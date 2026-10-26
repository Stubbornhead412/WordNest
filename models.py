from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Word(db.Model):
    """单词模型"""
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), unique=True, nullable=False)
    marked = db.Column(db.Boolean, default=False)
    
    definitions = db.relationship('Definition', backref='word', lazy=True, cascade="all, delete-orphan")
    
    def to_dict(self):
        """将单词转换为字典格式，与原JSON结构兼容"""
        return {
            'word': self.word,
            'marked': self.marked,
            'definitions': [definition.to_dict() for definition in self.definitions]
        }
    
    @staticmethod
    def from_dict(word_dict):
        """从字典创建单词对象"""
        word = Word(word=word_dict['word'], marked=word_dict.get('marked', False))
        for def_dict in word_dict['definitions']:
            definition = Definition.from_dict(def_dict)
            word.definitions.append(definition)
        return word

class Definition(db.Model):
    """单词定义模型"""
    id = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('word.id'), nullable=False)
    part_of_speech = db.Column(db.String(20), nullable=False)
    meaning = db.Column(db.Text, nullable=False)
    example = db.Column(db.Text, nullable=True)
    note = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        """将定义转换为字典格式，与原JSON结构兼容"""
        return {
            'part_of_speech': self.part_of_speech,
            'meaning': self.meaning,
            'example': self.example or "",
            'note': self.note or ""
        }
    
    @staticmethod
    def from_dict(definition_dict):
        """从字典创建定义对象"""
        return Definition(
            part_of_speech=definition_dict['part_of_speech'],
            meaning=definition_dict['meaning'],
            example=definition_dict.get('example', ""),
            note=definition_dict.get('note', "")
        ) 
class StudyRecord(db.Model):
    """每日学习记录

    存放在独立数据库 study_data/study.db（__bind_key__ = 'study'），
    与具体词库解耦：切换单词列表不会影响学习统计。

    同一单词在同一天只保留一行，重复学习则累加 count，
    这样"今天学了几个词"统计的是去重后的单词数。
    """
    __bind_key__ = 'study'

    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False, index=True)
    list_name = db.Column(db.String(100), default='words')
    study_date = db.Column(db.Date, nullable=False, index=True)
    count = db.Column(db.Integer, default=1)
    first_at = db.Column(db.DateTime)
    last_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('word', 'list_name', 'study_date', name='uq_study_word_day'),
    )

    def to_dict(self):
        return {
            'word': self.word,
            'list_name': self.list_name,
            'study_date': self.study_date.strftime('%Y-%m-%d') if self.study_date else '',
            'count': self.count or 1,
            'last_at': self.last_at.strftime('%Y-%m-%d %H:%M:%S') if self.last_at else '',
        }


class Note(db.Model):
    """学习笔记

    和 StudyRecord 一样放在 study_data/study.db（__bind_key__ = 'study'），
    用来随手记下背单词时的想法、老师讲的点、易错总结等。

    这些笔记载入 AI 助教的上下文，作为它的"参考资料"。
    """
    __bind_key__ = 'study'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='')
    content = db.Column(db.Text, nullable=False)
    # 可选：这条笔记是针对哪个单词写的
    word = db.Column(db.String(100), default='', index=True)
    tags = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title or '',
            'content': self.content or '',
            'word': self.word or '',
            'tags': self.tags or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
            # 列表预览用正文（不是标题，避免和无标题时的标题行重复）
            'preview': ' '.join((self.content or '').split())[:70],
        }


class WordCycleMeta(db.Model):
    """抽词"轮次"元信息

    每个池子（全部词 / 只看星标 / 复习某一天）一行，记录：
    - cycle：第几轮
    - seed：这一轮的洗牌种子（同轮内固定，顺序稳定但不按字母）
    - last_word：上一张发出的牌，用于避免跨轮连续重复

    放在独立的 study_data/cycle.db（__bind_key__ = 'cycle'）。
    这个库可以丢：极端情况下（断电/崩溃）最多少记几条"已抽过"，
    顶多重复出现几个词，不影响词库、笔记和学习记录。
    """
    __bind_key__ = 'cycle'

    pool_key = db.Column(db.String(200), primary_key=True)
    cycle = db.Column(db.Integer, default=1)
    seed = db.Column(db.String(64), default='')
    last_word = db.Column(db.String(100), default='')
    updated_at = db.Column(db.DateTime)


class WordCycleServed(db.Model):
    """本轮已经发过的单词

    抽词不再依赖"排序位置游标"，而是记录"这一轮发过哪些词"。
    这样词库增删都不会让顺序错乱：
    - 新加的词没有记录 → 立刻进入本轮候选
    - 删掉的词自然不再出现
    - 同一轮靠唯一约束保证不重复
    """
    __bind_key__ = 'cycle'

    id = db.Column(db.Integer, primary_key=True)
    pool_key = db.Column(db.String(200), nullable=False, index=True)
    word = db.Column(db.String(100), nullable=False)
    cycle = db.Column(db.Integer, nullable=False)
    served_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('pool_key', 'word', name='uq_cycle_pool_word'),
    )
