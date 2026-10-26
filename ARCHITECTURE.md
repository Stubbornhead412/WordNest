# WordNest 架构设计文档

## 📋 目录

- [架构概述](#架构概述)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [核心模块](#核心模块)
- [数据流](#数据流)
- [扩展指南](#扩展指南)

## 架构概述

WordNest 采用**三层架构模式（Three-Tier Architecture）**，实现了关注点分离和模块化设计。

```
┌─────────────────────────────────────────┐
│         表示层 (Presentation)           │
│       Templates + Static Files          │
└────────────────┬────────────────────────┘
                 │ HTTP Request/Response
┌────────────────▼────────────────────────┐
│          路由层 (Routes)                 │
│    Flask Blueprints - 请求处理           │
└────────────────┬────────────────────────┘
                 │ Function Calls
┌────────────────▼────────────────────────┐
│          服务层 (Services)               │
│      业务逻辑 - 可复用组件               │
└────────────────┬────────────────────────┘
                 │ ORM Operations
┌────────────────▼────────────────────────┐
│          数据层 (Models)                 │
│     SQLAlchemy ORM - 数据模型            │
└────────────────┬────────────────────────┘
                 │ SQL Queries
┌────────────────▼────────────────────────┐
│           数据库 (Database)              │
│          SQLite / PostgreSQL             │
└─────────────────────────────────────────┘
```

## 技术栈

### 后端框架
- **Flask 2.2.5**: 轻量级Web框架
- **Flask-SQLAlchemy 3.0.3**: ORM工具
- **SQLite**: 默认数据库（支持PostgreSQL/MySQL）

### AI集成
- **Ollama**: 本地大语言模型服务
- **Qwen 2.5**: 3B参数模型，用于例句和笔记生成
- **DeepSeek API**: 知识图谱生成

### 前端技术
- **HTML5/CSS3**: 响应式UI
- **JavaScript/jQuery**: 交互逻辑
- **Vis.js**: 知识图谱可视化

## 目录结构

```
wordList/
├── app.py                    # 应用入口（工厂模式）
├── config.py                 # 配置管理
├── models.py                 # 数据模型
│
├── routes/                   # 路由层
│   ├── __init__.py
│   ├── word_routes.py        # 单词CRUD + 自测
│   ├── graph_routes.py       # 知识图谱
│   └── api_routes.py         # RESTful API
│
├── services/                 # 服务层
│   ├── __init__.py
│   ├── word_service.py       # 单词业务逻辑
│   ├── llm_service.py        # AI服务
│   └── graph_service.py      # 图谱服务
│
├── utils/                    # 工具模块
│   ├── __init__.py
│   ├── constants.py          # 常量定义
│   └── settings.py           # 设置管理
│
├── templates/                # HTML模板
├── static/                   # 静态资源
└── instance/                 # 数据库文件
```

## 核心模块

### 1. 应用工厂 (app.py)

使用工厂模式创建应用实例，支持不同环境配置：

```python
def create_app(config_name=None):
    """创建并配置Flask应用"""
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    db.init_app(app)
    
    # 注册蓝图
    register_blueprints(app)
    
    return app
```

**优势**:
- 支持多环境配置（开发/生产）
- 便于单元测试
- 延迟初始化，提高灵活性

### 2. 路由层 (routes/)

使用Flask Blueprint组织路由，实现模块化：

#### word_routes.py - 单词管理
```python
word_bp = Blueprint('word', __name__)

@word_bp.route('/add_word', methods=['POST'])
def add_word():
    data = request.json
    if WordService.add_word(data['word'], data['definitions']):
        return jsonify({'success': True})
    return jsonify({'error': '单词已存在'}), 400
```

#### graph_routes.py - 知识图谱
```python
graph_bp = Blueprint('graph', __name__)

@graph_bp.route('/knowledge_graph')
def knowledge_graph():
    # 渲染图谱页面
    pass
```

#### api_routes.py - RESTful API
```python
api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/graph_data')
def graph_data():
    # 返回JSON数据
    pass
```

**职责**:
- 处理HTTP请求和响应
- 参数验证
- 调用服务层方法
- 错误处理

### 3. 服务层 (services/)

封装业务逻辑，提供可复用的服务：

#### WordService - 单词服务
```python
class WordService:
    @staticmethod
    def add_word(word_str, definitions, marked=False):
        """添加新单词"""
        if WordService.find_word(word_str):
            return False
        # 业务逻辑
        return True
    
    @staticmethod
    def get_random_word(prev_word=None, marked_only=False):
        """获取随机单词"""
        # 智能选词逻辑
        pass
```

#### LLMService - AI服务
```python
class LLMService:
    @staticmethod
    def generate_example(word, part_of_speech, meaning):
        """使用本地AI生成例句"""
        response = ollama.chat(model='qwen2.5:3b', messages=[...])
        return response['message']['content']
```

#### GraphService - 图谱服务
```python
class GraphService:
    @staticmethod
    def generate_word_relations_using_deepseek(focus_word, relation_type, depth):
        """调用DeepSeek API生成单词关系"""
        # API调用逻辑
        pass
    
    @staticmethod
    def build_graph_data(focus_word, relations_data):
        """构建可视化图谱数据"""
        # 数据转换逻辑
        pass
```

**职责**:
- 实现核心业务逻辑
- 与第三方服务交互（AI API）
- 数据处理和转换
- 可被多个路由复用

### 4. 数据层 (models.py)

使用SQLAlchemy ORM定义数据模型：

```python
class Word(db.Model):
    """单词模型"""
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), unique=True, nullable=False)
    marked = db.Column(db.Boolean, default=False)
    
    definitions = db.relationship('Definition', backref='word', 
                                 lazy=True, cascade="all, delete-orphan")

class Definition(db.Model):
    """定义模型"""
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    part_of_speech = db.Column(db.String(20), nullable=False)
    meaning = db.Column(db.Text, nullable=False)
    example = db.Column(db.Text, nullable=True)
    note = db.Column(db.Text, nullable=True)
```

**关系设计**:
- 一对多关系：一个单词可有多个定义
- 级联删除：删除单词时自动删除其定义

### 5. 配置管理 (config.py)

集中管理应用配置：

```python
class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'default-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///words.db'
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

class DevelopmentConfig(Config):
    """开发环境"""
    DEBUG = True

class ProductionConfig(Config):
    """生产环境"""
    DEBUG = False
```

**特点**:
- 环境变量优先
- 支持多环境配置
- 敏感信息外部化

## 数据流

### 添加单词流程

```
1. 用户提交表单
   ↓
2. word_routes.add_word() 接收请求
   ↓
3. 调用 WordService.add_word()
   ↓
4. WordService 检查单词是否存在
   ↓
5. 创建 Word 和 Definition 对象
   ↓
6. 保存到数据库
   ↓
7. 返回 JSON 响应
   ↓
8. 前端更新界面
```

### AI生成例句流程

```
1. 用户点击"生成例句"
   ↓
2. AJAX 请求到 /generate_example
   ↓
3. word_routes.generate_example() 处理
   ↓
4. 调用 LLMService.generate_example()
   ↓
5. LLMService 调用 Ollama API
   ↓
6. Ollama 返回生成的例句
   ↓
7. 清理和格式化文本
   ↓
8. 返回 JSON 响应
   ↓
9. 前端填充到表单
```

### 知识图谱生成流程

```
1. 用户访问 /knowledge_graph?word=test
   ↓
2. graph_routes.knowledge_graph() 处理
   ↓
3. 调用 GraphService.generate_word_relations_using_deepseek()
   ↓
4. GraphService 调用 DeepSeek API
   ↓
5. 解析API返回的JSON数据
   ↓
6. 调用 GraphService.build_graph_data() 构建图谱
   ↓
7. 将数据传递给模板
   ↓
8. 渲染HTML页面
   ↓
9. 前端使用 Vis.js 可视化
```

## 扩展指南

### 添加新功能的步骤

假设要添加"单词收藏夹"功能：

#### 1. 更新数据模型
```python
# models.py
class Word(db.Model):
    # ... 现有字段
    favorite = db.Column(db.Boolean, default=False)  # 新增字段
```

#### 2. 添加服务层方法
```python
# services/word_service.py
class WordService:
    @staticmethod
    def toggle_favorite(word_str):
        """切换收藏状态"""
        word = WordService.find_word(word_str)
        if not word:
            return False
        word.favorite = not word.favorite
        db.session.commit()
        return True
```

#### 3. 添加路由
```python
# routes/word_routes.py
@word_bp.route('/favorite/<word>', methods=['POST'])
def favorite_word(word):
    if WordService.toggle_favorite(word):
        return jsonify({'success': True})
    return jsonify({'error': '操作失败'}), 400
```

#### 4. 更新前端
```javascript
// static/script.js
function toggleFavorite(word) {
    fetch(`/favorite/${word}`, {method: 'POST'})
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateFavoriteIcon();
            }
        });
}
```

### 添加新的AI服务

假设要集成翻译API：

#### 1. 创建服务类
```python
# services/translation_service.py
class TranslationService:
    @staticmethod
    def translate(text, target_lang='zh'):
        """翻译文本"""
        # 调用翻译API
        pass
```

#### 2. 在配置中添加API密钥
```python
# config.py
class Config:
    TRANSLATION_API_KEY = os.environ.get('TRANSLATION_API_KEY', '')
```

#### 3. 添加路由
```python
# routes/api_routes.py
@api_bp.route('/translate', methods=['POST'])
def translate():
    data = request.json
    result = TranslationService.translate(data['text'])
    return jsonify({'translation': result})
```

## 最佳实践

### 代码组织
1. ✅ **单一职责**: 每个模块只负责一个功能
2. ✅ **依赖注入**: 服务层不依赖具体实现
3. ✅ **错误处理**: 统一的错误处理机制
4. ✅ **日志记录**: 使用 `current_app.logger`

### 安全性
1. ✅ **环境变量**: 所有敏感信息使用环境变量
2. ✅ **输入验证**: 验证所有用户输入
3. ✅ **SQL注入防护**: 使用ORM参数化查询
4. ✅ **CSRF保护**: Flask-WTF提供保护

### 性能优化
1. ✅ **数据库索引**: 在常用查询字段添加索引
2. ✅ **查询优化**: 使用 eager loading 减少N+1查询
3. ✅ **缓存**: 对频繁访问的数据使用缓存
4. ✅ **异步处理**: 耗时操作使用后台任务

## 总结

WordNest的架构设计遵循以下原则：

- **分层清晰**: 三层架构，职责明确
- **模块化**: Blueprint + Service模式
- **可扩展**: 工厂模式支持灵活配置
- **可维护**: 代码组织合理，易于理解
- **可测试**: 业务逻辑与框架解耦

这种架构使得项目能够轻松应对功能扩展和维护需求。

