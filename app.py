"""
Flask应用主入口
使用应用工厂模式
"""
import os
import sqlite3 as _sqlite3

from flask import Flask, session, g
from sqlalchemy import event as _sa_event
from sqlalchemy.engine import Engine as _SaEngine

from config import config
from models import db

# SQLite 优化说明：
# 数据目录（instance/、study_data/）挂在 Windows 上，Docker 用的是 9p/drvfs，
# 不支持 SQLite 的 WAL 共享内存（WAL 库被第二个进程打开会报 unable to open database file），
# 所以普通数据库保持默认回滚日志模式（每次写入约 20ms，用户数据安全）。
# 只有"抽词轮转状态"这个可丢弃的小库用 MEMORY 日志 + 关闭同步（约 4ms），
# 它的代价是最坏情况丢几条"已抽过"记录（顶多重复出现一个词），不影响词库/笔记/学习记录。
_cycle_pragma_registered = False


def _register_sqlite_pragmas():
    global _cycle_pragma_registered
    if _cycle_pragma_registered:
        return
    _cycle_pragma_registered = True

    @_sa_event.listens_for(_SaEngine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        if not isinstance(dbapi_connection, _sqlite3.Connection):
            return
        try:
            cur = dbapi_connection.cursor()
            cur.execute("PRAGMA busy_timeout=5000")
            # 判断是不是轮转状态库
            try:
                dbs = [row[2] or '' for row in cur.execute("PRAGMA database_list").fetchall()]
            except Exception:
                dbs = []
            if any(p.endswith('cycle.db') for p in dbs):
                cur.execute("PRAGMA journal_mode=MEMORY")
                cur.execute("PRAGMA synchronous=OFF")
            cur.close()
        except Exception:
            pass


def create_app(config_name=None):
    """
    应用工厂函数
    
    Args:
        config_name: 配置名称 ('development', 'production', 'default')
        
    Returns:
        Flask应用实例
    """
    # 创建Flask应用
    app = Flask(__name__)

    # SQLite 连接优化（WAL + NORMAL 同步），必须在建连接之前注册
    _register_sqlite_pragmas()

    # 加载配置
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    app.config.from_object(config[config_name])
    
    # 确保instance文件夹存在
    instance_folder = app.config.get('INSTANCE_FOLDER', os.path.join(os.path.dirname(__file__), 'instance'))
    if not os.path.exists(instance_folder):
        os.makedirs(instance_folder)
    
    # 设置初始数据库 URI（使用默认的 words 列表）
    # 不使用 ListService.get_default_list()，因为此时还没有应用上下文
    default_db_path = os.path.join(instance_folder, 'words.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{default_db_path}'

    # 配置聊天 / 学习记录 / 抽词轮转 三个独立库（使用BINDS功能，与单词数据库分开）
    # 重要：必须在 db.init_app(app) 之前设置 BINDS
    chat_db_uri = config[config_name].get_chat_database_uri()
    study_db_uri = config[config_name].get_study_database_uri()
    cycle_db_uri = config[config_name].get_cycle_database_uri()
    app.config['SQLALCHEMY_BINDS'] = {
        'chat': chat_db_uri,
        'study': study_db_uri,
        'cycle': cycle_db_uri,
    }
    
    # 初始化单词数据库
    db.init_app(app)
    
    # 添加请求前处理函数，根据session中的当前列表动态切换数据库
    @app.before_request
    def before_request():
        """在每个请求之前，根据当前选中的列表切换数据库"""
        from services.list_service import ListService
        from sqlalchemy import create_engine
        
        # 获取当前列表名称
        current_list = session.get('current_list')
        
        # 如果没有设置当前列表，使用默认列表
        if not current_list:
            current_list = ListService.get_default_list()
            session['current_list'] = current_list
        
        # 检查列表是否存在
        if not ListService.list_exists(current_list):
            current_list = ListService.get_default_list()
            session['current_list'] = current_list
        
        # 动态设置数据库URI
        target_uri = config[config_name].get_database_uri(current_list)
        
        # 检查是否需要切换数据库
        current_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        
        if current_uri != target_uri:
            # 更新配置
            app.config['SQLALCHEMY_DATABASE_URI'] = target_uri
            
            # Flask-SQLAlchemy 3.x: 正确地切换数据库
            try:
                # 移除当前session
                db.session.remove()
                
                # 处理引擎切换 - Flask-SQLAlchemy 3.x 方式
                # 只替换默认引擎（None）：必须保留 chat / study 等 bind 的引擎，
                # 否则切换词表后这些独立数据库会取不到引擎而报错。
                if hasattr(db, 'engines'):
                    old_engine = db.engines.get(None)
                    if old_engine is not None:
                        old_engine.dispose()
                
                # 创建新引擎并添加到引擎字典
                # Flask-SQLAlchemy 3.x 使用 None 作为默认数据库的 key
                new_engine = create_engine(
                    target_uri,
                    echo=app.config.get('SQLALCHEMY_ECHO', False),
                    pool_pre_ping=True
                )
                db.engines[None] = new_engine
                
            except Exception as e:
                # 如果切换失败，记录错误
                print(f"数据库切换错误: {e}")
                import traceback
                traceback.print_exc()

        # 访问密码（只有设置了 WORDNEST_PASSWORD 才生效，留空则完全不干预）
        from utils.auth import check_access
        denied = check_access()
        if denied is not None:
            return denied

    # 注册蓝图
    from routes import register_blueprints
    register_blueprints(app)

    # gzip 压缩（手机 / 公网访问时能省掉大量传输时间）
    # 注意：mimetype 白名单里不含 text/event-stream，AI 流式回答不会被压缩/缓冲
    try:
        from flask_compress import Compress
        app.config.setdefault('COMPRESS_MIMETYPES', [
            'text/html', 'text/css', 'text/plain', 'text/xml',
            'application/json', 'application/javascript', 'image/svg+xml',
        ])
        app.config.setdefault('COMPRESS_MIN_SIZE', 1024)
        app.config.setdefault('COMPRESS_ALGORITHM', ['gzip'])
        Compress(app)
    except ImportError:
        print("提示：未安装 flask-compress，跳过响应压缩")
    
    # 初始化数据库（在应用上下文中）
    with app.app_context():
        # 导入所有模型（包括 chat_models），确保Flask-SQLAlchemy知道所有表
        from models import Word, StudyRecord, Note, WordCycleMeta, WordCycleServed
        from chat_models import Conversation, Message
        
        # 创建所有表（如果不存在）
        # db.create_all()会自动创建所有数据库中的表，包括bind='chat'的表
        db.create_all()
        
        # 如果数据库是空的，但JSON文件存在，则导入数据
        try:
            if Word.query.count() == 0 and os.path.exists('words.json'):
                migrate_json_to_db()
        except Exception as e:
            print(f"初始化数据库时出错: {e}")
            # 如果查询失败，可能是因为引擎还未正确初始化，忽略这个错误
    
    return app


def migrate_json_to_db():
    """从JSON文件迁移数据到数据库"""
    import json
    from models import Word
    
    with open('words.json', 'r', encoding='utf-8') as f:
        words_data = json.load(f)
        
    for word_data in words_data:
        word = Word.from_dict(word_data)
        db.session.add(word)
    
    db.session.commit()
    print(f"成功导入 {len(words_data)} 个单词到数据库")


# 创建应用实例
app = create_app()


if __name__ == '__main__':
    # 从环境变量获取调试模式设置
    debug_mode = os.environ.get('DEBUG', 'True').lower() == 'true'
    app.run(debug=debug_mode)
