"""
抽词轮转服务（与词数无关，支持词库随时增删）

思路升级：不再记录"排到第几张牌"，而是记录"本轮已经发过哪些词"。

为什么这样更稳：
- 新增单词：它在"已发集合"里没有记录 → 下一抽就可能出现，不用等下一轮
- 删除单词：已发记录里残留也无害（取词只按当前词池过滤）
- 轮次边界：新一轮第一张不等于上一轮最后一张
- 一轮内不重复：靠唯一约束 (pool_key, word) 保证
- 与词数无关：400 词和 4 万词走同一套逻辑，复杂度只跟"本轮剩余"有关

数据落在 study_data/study.db（__bind_key__ = 'study'）：
- word_cycle_meta   每个池子一行（轮次 / 种子 / 上一张）
- word_cycle_served 每个池子每轮每个词一行
"""
import hashlib
import random
from datetime import datetime

from flask import current_app

from models import db, WordCycleMeta, WordCycleServed


def _rank(seed, word):
    """确定性的乱序键：同一轮内固定，保证"看起来随机但可复现" """
    return hashlib.sha1(f'{seed}|{word}'.encode('utf-8')).hexdigest()


class CycleService:
    """按轮发牌，词库变化也能正确衔接"""

    @staticmethod
    def _meta(pool_key):
        meta = db.session.get(WordCycleMeta, pool_key)
        if meta is None:
            meta = WordCycleMeta(
                pool_key=pool_key,
                cycle=1,
                seed=str(random.randint(1, 10 ** 9)),
                last_word='',
                updated_at=datetime.now(),
            )
            db.session.add(meta)
            db.session.flush()
        elif not meta.seed:
            meta.seed = str(random.randint(1, 10 ** 9))
        return meta

    @staticmethod
    def _served_words(pool_key):
        rows = WordCycleServed.query.filter_by(pool_key=pool_key).all()
        return {r.word for r in rows}

    @staticmethod
    def next_word(pool, pool_key):
        """
        从 pool 里按轮转取下一个词

        Args:
            pool: 候选单词（字符串列表），可以随时变化
            pool_key: 池子标识，如 'words|all' / 'words|marked' / 'review|words|2026-10-24'

        Returns:
            选中的单词；pool 为空返回 None
        """
        words = [w for w in (pool or []) if w]
        if not words:
            return None
        if len(words) == 1:
            # 只有一个词，直接返回（跨轮重复不可避免）
            return words[0]

        try:
            meta = CycleService._meta(pool_key)
            served = CycleService._served_words(pool_key)
            unserved = [w for w in words if w not in served]

            if not unserved:
                # 本轮发完 → 开启新一轮
                meta.cycle = (meta.cycle or 1) + 1
                meta.seed = str(random.randint(1, 10 ** 9))
                WordCycleServed.query.filter_by(pool_key=pool_key).delete()
                db.session.flush()
                unserved = list(words)

            unserved.sort(key=lambda w: _rank(meta.seed, w))

            # 新一轮第一张不要和上一轮最后一张相同：
            # 让位给第二张，被让掉的那张本轮仍然"未发"，下次会补上。
            if meta.last_word and len(unserved) > 1 and unserved[0] == meta.last_word:
                unserved[0], unserved[1] = unserved[1], unserved[0]

            word = unserved[0]
            db.session.add(WordCycleServed(
                pool_key=pool_key, word=word, cycle=meta.cycle, served_at=datetime.now()))
            meta.last_word = word
            meta.updated_at = datetime.now()
            db.session.commit()
            return word

        except Exception as e:
            db.session.rollback()
            try:
                current_app.logger.warning(f'轮转抽词失败，退回随机: {e}')
            except Exception:
                pass
            return random.choice(words)

    @staticmethod
    def clear_pool(pool_key):
        """清掉某个池子的轮次状态（重新开始一轮）"""
        try:
            WordCycleServed.query.filter_by(pool_key=pool_key).delete()
            meta = db.session.get(WordCycleMeta, pool_key)
            if meta:
                meta.cycle = (meta.cycle or 1) + 1
                meta.seed = str(random.randint(1, 10 ** 9))
                meta.last_word = ''
            db.session.commit()
        except Exception:
            db.session.rollback()

    @staticmethod
    def clear_pools_like(prefix, keep=None):
        """清理某类池子（例如换了复习日期后清掉旧的复习轮次）"""
        try:
            metas = WordCycleMeta.query.filter(
                WordCycleMeta.pool_key.like(prefix + '%')).all()
            removed = 0
            for meta in metas:
                if keep and meta.pool_key == keep:
                    continue
                WordCycleServed.query.filter_by(pool_key=meta.pool_key).delete()
                db.session.delete(meta)
                removed += 1
            db.session.commit()
            return removed
        except Exception:
            db.session.rollback()
            return 0

    @staticmethod
    def progress(pool_size, pool_key):
        """本轮进度：已发几个 / 池子多大（给前端显示用）"""
        try:
            served = WordCycleServed.query.filter_by(pool_key=pool_key).count()
            meta = db.session.get(WordCycleMeta, pool_key)
            return {
                'served': served,
                'total': pool_size,
                'cycle': (meta.cycle if meta else 1) or 1,
            }
        except Exception:
            return {'served': 0, 'total': pool_size, 'cycle': 1}
