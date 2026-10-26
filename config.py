"""
应用配置文件
"""
import os


class Config:
    """基础配置类"""
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'word_list_secret_key'
    
    # 数据库配置
    # 默认数据库URI，可以通过set_database_uri动态修改
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///words.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # 设置为True可以看到SQL语句
    # Instance文件夹路径（存放数据库文件）
    INSTANCE_FOLDER = os.path.join(os.path.dirname(__file__), 'instance')
    
    # Chat数据库文件夹路径（存放聊天记录数据库，与单词数据库分开）
    CHAT_DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'chat_data')
    
    # 学习记录数据库文件夹（存放每日学习记录，与单词库、聊天库分开）
    STUDY_DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'study_data')
    
    # Deepseek API配置
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')  # 敏感信息已移除
    DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com  ')

    # 访问密码：留空=不启用；设置后需要先登录（用于手机/远程访问时保护数据）
    ACCESS_PASSWORD = os.environ.get('WORDNEST_PASSWORD', '')

    # 容器出网代理：宿主机开了 Clash 等代理时，容器直连会被掐断，需要走这个端口。
    # 留空则只直连；设了但代理没开时会自动回落直连。
    OUTBOUND_PROXY = os.environ.get('WORDNEST_PROXY', '')
    
    # 应用配置
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    @staticmethod
    def get_database_uri(list_name='words'):
        """
        根据列表名称生成数据库URI
        
        Args:
            list_name: 列表名称，默认为'words'
            
        Returns:
            数据库URI字符串
        """
        instance_folder = Config.INSTANCE_FOLDER
        db_filename = f'{list_name}.db'
        db_path = os.path.join(instance_folder, db_filename)
        return f'sqlite:///{db_path}'
    
    @staticmethod
    def get_chat_database_uri():
        """
        获取聊天数据库URI
        
        Returns:
            聊天数据库URI字符串
        """
        chat_folder = Config.CHAT_DATA_FOLDER
        # 确保文件夹存在
        if not os.path.exists(chat_folder):
            os.makedirs(chat_folder)
        db_path = os.path.join(chat_folder, 'chat.db')
        return f'sqlite:///{db_path}'
    
    @staticmethod
    def get_study_database_uri():
        """
        获取学习记录数据库URI
        
        Returns:
            学习记录数据库URI字符串
        """
        study_folder = Config.STUDY_DATA_FOLDER
        if not os.path.exists(study_folder):
            os.makedirs(study_folder)
        db_path = os.path.join(study_folder, 'study.db')
        return f'sqlite:///{db_path}'

    @staticmethod
    def get_cycle_database_uri():
        """
        获取"抽词轮转状态"数据库URI

        单独一个库：数据可丢弃（最坏情况重复出现几个词），
        所以可以用 MEMORY 日志 + 关闭同步来换取写入速度，
        不会影响词库/笔记/学习记录这些真正重要的数据。
        """
        study_folder = Config.STUDY_DATA_FOLDER
        if not os.path.exists(study_folder):
            os.makedirs(study_folder)
        db_path = os.path.join(study_folder, 'cycle.db')
        return f'sqlite:///{db_path}'


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
