"""
学习记录服务层

按天记录"今天学过哪些单词"，并提供：
- 汇总统计（今天 / 近 7 天 / 累计去重词数 / 学习天数）
- 每日时间序列（用于柱状图）
- 每日单词明细（用于"按天目录"复习）

数据存放在独立的 study_data/study.db（__bind_key__ = 'study'），
因此切换单词列表不会影响统计；同一词同一天只存一行，重复学习累加次数。
"""
from datetime import date, datetime, timedelta

from flask import current_app, session
from sqlalchemy import func

from models import db, StudyRecord

WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


class StudyService:
    """每日学习记录服务"""

    @staticmethod
    def _current_list():
        """取当前单词列表名（默认 words）"""
        try:
            return session.get('current_list') or 'words'
        except Exception:
            return 'words'

    @staticmethod
    def record(word, action='view', list_name=None):
        """
        记录一次"学过这个单词"

        Args:
            word: 单词
            action: 触发动作（view / mark / unmark / review），仅作标识
            list_name: 词表名，默认取 session 中的当前列表

        Returns:
            成功 True，失败 False（记录失败不影响主流程）
        """
        word = (word or '').strip()
        if not word:
            return False
        try:
            if not list_name:
                list_name = StudyService._current_list()
            today = date.today()
            now = datetime.now()

            row = StudyRecord.query.filter_by(
                word=word, list_name=list_name, study_date=today
            ).first()

            if row is None:
                db.session.add(StudyRecord(
                    word=word,
                    list_name=list_name,
                    study_date=today,
                    count=1,
                    first_at=now,
                    last_at=now,
                ))
            else:
                row.count = (row.count or 1) + 1
                row.last_at = now

            db.session.commit()
            return True
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            try:
                current_app.logger.warning(f"记录学习日志失败（不影响使用）: {e}")
            except Exception:
                pass
            return False

    @staticmethod
    def summary():
        """今日 / 近 7 天 / 累计 统计"""
        try:
            today = date.today()
            week_start = today - timedelta(days=6)

            today_count = db.session.query(func.count(StudyRecord.id)).filter(
                StudyRecord.study_date == today
            ).scalar() or 0

            week_count = db.session.query(func.count(StudyRecord.id)).filter(
                StudyRecord.study_date >= week_start
            ).scalar() or 0

            total_words = db.session.query(
                func.count(func.distinct(StudyRecord.word))
            ).scalar() or 0

            total_days = db.session.query(
                func.count(func.distinct(StudyRecord.study_date))
            ).scalar() or 0

            return {
                'today': int(today_count),
                'week': int(week_count),
                'total_words': int(total_words),
                'total_days': int(total_days),
            }
        except Exception as e:
            try:
                current_app.logger.warning(f"读取学习统计失败: {e}")
            except Exception:
                pass
            return {'today': 0, 'week': 0, 'total_words': 0, 'total_days': 0}

    @staticmethod
    def daily_series(days=30):
        """
        最近 N 天的每日学习量（补零），用于时间序列柱状图

        Returns:
            [{'date': '2026-10-20', 'label': '10-20', 'weekday': '周一', 'count': 12}, ...]
        """
        days = max(1, int(days or 30))
        today = date.today()
        start = today - timedelta(days=days - 1)

        counts = {}
        try:
            rows = db.session.query(
                StudyRecord.study_date, func.count(StudyRecord.id)
            ).filter(StudyRecord.study_date >= start).group_by(StudyRecord.study_date).all()
            counts = {r[0]: int(r[1]) for r in rows if r[0]}
        except Exception as e:
            try:
                current_app.logger.warning(f"读取每日序列失败: {e}")
            except Exception:
                pass

        series = []
        for i in range(days):
            day = start + timedelta(days=i)
            series.append({
                'date': day.strftime('%Y-%m-%d'),
                'label': day.strftime('%m-%d'),
                'weekday': WEEKDAYS[day.weekday()],
                'count': counts.get(day, 0),
                'is_today': day == today,
            })
        return series

    @staticmethod
    def days_with_words(limit=60):
        """
        按天倒序列出学习记录（"目录"视图），并带上当天的单词明细

        Returns:
            [{'date','label','weekday','count','words':[{'word','pos','meaning','marked','times'}]}]
        """
        limit_days = max(1, int(limit or 60))
        try:
            dates = db.session.query(
                StudyRecord.study_date, func.count(StudyRecord.id)
            ).group_by(StudyRecord.study_date).order_by(
                StudyRecord.study_date.desc()
            ).limit(limit_days).all()
        except Exception as e:
            try:
                current_app.logger.warning(f"读取每日目录失败: {e}")
            except Exception:
                pass
            return []

        if not dates:
            return []

        day_map = []
        for day, count in dates:
            if day is None:
                continue
            day_map.append({
                'date': day.strftime('%Y-%m-%d'),
                'label': day.strftime('%m月%d日'),
                'weekday': WEEKDAYS[day.weekday()],
                'count': int(count),
                'words': [],
            })

        start_day = dates[-1][0]
        try:
            records = StudyRecord.query.filter(
                StudyRecord.study_date >= start_day
            ).order_by(StudyRecord.study_date.desc(), StudyRecord.last_at.asc()).all()
        except Exception:
            records = []

        by_date = {}
        for r in records:
            if r.study_date is None:
                continue
            key = r.study_date.strftime('%Y-%m-%d')
            by_date.setdefault(key, []).append(r)

        # 补齐释义（来自当前词表；跨词表的词只显示单词本身）
        all_words = [r.word for r in records]
        meanings = {}
        if all_words:
            try:
                from models import Word
                for w in Word.query.filter(Word.word.in_(all_words)).all():
                    first = w.definitions[0] if w.definitions else None
                    meanings[w.word] = {
                        'pos': first.part_of_speech if first else '',
                        'meaning': first.meaning if first else '',
                        'marked': bool(w.marked),
                    }
            except Exception:
                meanings = {}

        for item in day_map:
            for r in by_date.get(item['date'], []):
                info = meanings.get(r.word, {})
                item['words'].append({
                    'word': r.word,
                    'pos': info.get('pos', ''),
                    'meaning': info.get('meaning', ''),
                    'marked': info.get('marked', False),
                    'times': r.count or 1,
                })

        return day_map

    @staticmethod
    def word_texts_for_day(day_str):
        """取某一天学过的单词（用于"复习这一天"）"""
        try:
            day = datetime.strptime(day_str, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return []
        try:
            rows = StudyRecord.query.filter(StudyRecord.study_date == day).all()
            words, seen = [], set()
            for r in rows:
                if r.word and r.word not in seen:
                    seen.add(r.word)
                    words.append(r.word)
            return words
        except Exception:
            return []

    @staticmethod
    def has_any_record():
        """是否有任何记录（用于空状态提示）"""
        try:
            return db.session.query(StudyRecord.id).first() is not None
        except Exception:
            return False
