"""
笔记服务层

- 增删改查（存 study_data/study.db，__bind_key__ = 'study'）
- 给 AI 助教提供"最近笔记"上下文
"""
from datetime import datetime

from flask import current_app
from sqlalchemy import or_

from models import db, Note

MAX_CONTENT = 20000


class NotesService:
    """学习笔记的读写"""

    @staticmethod
    def create(content, title='', word='', tags=''):
        content = (content or '').strip()
        if not content:
            return None, '笔记内容不能为空'
        if len(content) > MAX_CONTENT:
            return None, f'笔记太长了（最多 {MAX_CONTENT} 字）'

        now = datetime.now()
        note = Note(
            title=(title or '').strip()[:200],
            content=content,
            word=(word or '').strip()[:100],
            tags=(tags or '').strip()[:200],
            created_at=now,
            updated_at=now,
        )
        try:
            db.session.add(note)
            db.session.commit()
            return note, None
        except Exception as e:
            db.session.rollback()
            NotesService._log(f'新建笔记失败: {e}')
            return None, '保存失败，请稍后重试'

    @staticmethod
    def update(note_id, content=None, title=None, word=None, tags=None):
        note = db.session.get(Note, note_id)
        if not note:
            return None, '笔记不存在'

        if content is not None:
            content = content.strip()
            if not content:
                return None, '笔记内容不能为空'
            if len(content) > MAX_CONTENT:
                return None, f'笔记太长了（最多 {MAX_CONTENT} 字）'
            note.content = content

        if title is not None:
            note.title = title.strip()[:200]
        if word is not None:
            note.word = word.strip()[:100]
        if tags is not None:
            note.tags = tags.strip()[:200]

        note.updated_at = datetime.now()
        try:
            db.session.commit()
            return note, None
        except Exception as e:
            db.session.rollback()
            NotesService._log(f'更新笔记失败: {e}')
            return None, '保存失败，请稍后重试'

    @staticmethod
    def delete(note_id):
        note = db.session.get(Note, note_id)
        if not note:
            return False
        try:
            db.session.delete(note)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            NotesService._log(f'删除笔记失败: {e}')
            return False

    @staticmethod
    def get(note_id):
        return db.session.get(Note, note_id)

    @staticmethod
    def list_notes(q='', word='', limit=200):
        """按关键词（标题/内容/单词/标签）搜索"""
        query = Note.query
        q = (q or '').strip()
        if q:
            like = f'%{q}%'
            query = query.filter(or_(
                Note.title.like(like),
                Note.content.like(like),
                Note.word.like(like),
                Note.tags.like(like),
            ))
        if word:
            query = query.filter(Note.word == word.strip())
        return query.order_by(Note.updated_at.desc()).limit(limit).all()

    @staticmethod
    def count():
        try:
            return Note.query.count()
        except Exception:
            return 0

    @staticmethod
    def recent_for_ai(limit=8, max_chars=240):
        """
        取最近几条笔记，压缩成一行一条的文本，供 AI 参考。
        超出 max_chars 的笔记会被截断并加省略号。
        """
        try:
            notes = Note.query.order_by(Note.updated_at.desc()).limit(limit).all()
        except Exception as e:
            NotesService._log(f'读取笔记失败: {e}')
            return '', 0

        lines = []
        for n in notes:
            body = (n.content or '').replace('\r', '').replace('\n', ' ')
            body = ' '.join(body.split())
            if len(body) > max_chars:
                body = body[:max_chars] + '…'
            prefix = f'[{(n.updated_at or n.created_at).strftime("%m-%d")}]'
            if n.word:
                prefix += f'(关于 {n.word})'
            if n.title:
                prefix += f' {n.title}：'
            lines.append(f'- {prefix}{body}')
        return '\n'.join(lines), NotesService.count()

    @staticmethod
    def _log(msg):
        try:
            current_app.logger.warning(msg)
        except Exception:
            pass
