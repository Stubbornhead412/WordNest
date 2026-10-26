"""
单词服务层
处理单词相关的业务逻辑
"""
import random
from flask import session

from models import db, Word, Definition
from sqlalchemy import or_

from services.cycle_service import CycleService


class WordService:
    """单词服务类"""
    
    @staticmethod
    def find_word(word_str):
        """查找指定单词"""
        return Word.query.filter_by(word=word_str).first()
    
    @staticmethod
    def get_all_words():
        """获取所有单词"""
        return Word.query.all()
    
    @staticmethod
    def get_words_with_definitions():
        """获取所有单词及其定义"""
        words = []
        for word in Word.query.all():
            word_dict = word.to_dict()
            # 获取所有定义
            definitions = []
            for definition in Definition.query.filter_by(word_id=word.id).all():
                definitions.append(definition.to_dict())
            word_dict['definitions'] = definitions
            words.append(word_dict)
        return words
    
    @staticmethod
    def get_random_word(prev_word=None, marked_only=False, pool=None, pool_key=None):
        """
        抽取下一个待背单词（按轮发牌，一轮内不重复）

        算法与词数无关，词库随时增删都不会错乱：
        - 记录"本轮发过哪些词"而不是"排到第几张"
        - 新加的词立刻进入本轮候选，删掉的词自然消失

        性能注意：这里只取"单词字符串"，不构造 Word ORM 对象
        （400 个 ORM 对象在每次点"下一个"时被创建是很浪费的）。

        Args:
            prev_word: 已废弃参数，保留只为兼容旧调用
            marked_only: 是否只从星标单词里抽
            pool: 直接指定候选词对象列表（复习某一天时用）
            pool_key: 池子标识；默认按"当前词表 + 是否只看星标"生成

        Returns:
            选中的单词字符串；没有可用单词时返回 None
        """
        if pool is not None:
            words = [w.word if hasattr(w, 'word') else str(w) for w in pool]
        else:
            query = Word.query
            if marked_only:
                query = query.filter_by(marked=True)
            # 只查 word 列，避免 ORM 实例化
            words = [row[0] for row in query.with_entities(Word.word).all()]

        if not words:
            return None

        if not pool_key:
            list_name = session.get('current_list') or 'words'
            pool_key = f"{list_name}|{'marked' if marked_only else 'all'}"

        return CycleService.next_word(words, pool_key)

    @staticmethod
    def cycle_progress(marked_only=False, pool=None, pool_key=None):
        """本轮抽词进度（给前端展示"本轮 12/400"用）"""
        if pool is not None:
            total = len(pool)
        elif marked_only:
            total = Word.query.filter_by(marked=True).count()
        else:
            total = Word.query.count()

        if not pool_key:
            list_name = session.get('current_list') or 'words'
            pool_key = f"{list_name}|{'marked' if marked_only else 'all'}"

        return CycleService.progress(total, pool_key)
    
    @staticmethod
    def add_word(word_str, definitions, marked=False):
        """
        添加新单词
        
        Args:
            word_str: 单词文本
            definitions: 定义列表
            marked: 是否标记
            
        Returns:
            添加成功返回True，单词已存在返回False
        """
        # 检查单词是否已存在
        if WordService.find_word(word_str):
            return False
        
        # 确保例句和笔记字段有值
        for definition in definitions:
            if 'example' not in definition or not definition.get('example', '').strip():
                definition['example'] = ""
            if 'note' not in definition or not definition.get('note', '').strip():
                definition['note'] = ""
        
        # 添加新单词
        word = Word.from_dict({
            'word': word_str,
            'definitions': definitions,
            'marked': marked
        })
        
        db.session.add(word)
        db.session.commit()
        return True
    
    @staticmethod
    def update_word(old_word_str, new_word_str, definitions):
        """
        更新单词
        
        Args:
            old_word_str: 原单词文本
            new_word_str: 新单词文本
            definitions: 定义列表
            
        Returns:
            更新成功返回True，单词不存在或新单词已被占用返回False
        """
        word_data = WordService.find_word(old_word_str)
        if not word_data:
            return False
        
        # 如果单词文本发生了变化，检查新单词是否与其他单词冲突
        if old_word_str != new_word_str:
            if WordService.find_word(new_word_str):
                return False
            word_data.word = new_word_str
        
        # 删除现有定义
        for definition in word_data.definitions:
            db.session.delete(definition)
        
        # 添加新定义
        for def_data in definitions:
            definition = Definition(
                part_of_speech=def_data['part_of_speech'],
                meaning=def_data['meaning'],
                example=def_data.get('example', ""),
                note=def_data.get('note', "")
            )
            word_data.definitions.append(definition)
        
        db.session.commit()
        return True
    
    @staticmethod
    def delete_word(word_str):
        """
        删除单词
        
        Args:
            word_str: 单词文本
            
        Returns:
            删除成功返回True，单词不存在返回False
        """
        word_data = WordService.find_word(word_str)
        if not word_data:
            return False
        
        db.session.delete(word_data)
        db.session.commit()
        return True
    
    @staticmethod
    def mark_word(word_str, marked=True):
        """
        标记或取消标记单词
        
        Args:
            word_str: 单词文本
            marked: True标记，False取消标记
            
        Returns:
            操作成功返回True，单词不存在返回False
        """
        word_data = WordService.find_word(word_str)
        if not word_data:
            return False
        
        word_data.marked = marked
        db.session.commit()
        return True
    
    @staticmethod
    def add_definition(word_str, definition_data):
        """
        为单词添加新定义
        
        Args:
            word_str: 单词文本
            definition_data: 定义数据字典
            
        Returns:
            添加成功返回True，单词不存在返回False
        """
        word_data = WordService.find_word(word_str)
        if not word_data:
            return False
        
        definition = Definition(
            part_of_speech=definition_data['part_of_speech'],
            meaning=definition_data['meaning'],
            example=definition_data.get('example', ""),
            note=definition_data.get('note', "")
        )
        
        word_data.definitions.append(definition)
        db.session.commit()
        return True
    
    @staticmethod
    def get_word_details(word_str):
        """
        获取单词详情（包括前后单词）
        
        Args:
            word_str: 单词文本
            
        Returns:
            包含当前单词、前一个单词、后一个单词的字典
        """
        # 获取所有单词并排序
        all_words = [w.word for w in Word.query.order_by(Word.word).all()]
        
        # 检查单词是否存在
        if word_str not in all_words:
            return None
        
        current_index = all_words.index(word_str)
        
        # 确定前一个和后一个单词
        prev_word = all_words[current_index - 1] if current_index > 0 else None
        next_word = all_words[current_index + 1] if current_index < len(all_words) - 1 else None
        
        # 获取当前单词的详情
        word_data = WordService.find_word(word_str)
        
        return {
            'current': word_data.to_dict(),
            'prev': prev_word,
            'next': next_word
        }
    
    @staticmethod
    def get_filtered_words(marked_only=False, sort_alphabetically=False):
        """
        获取筛选和排序后的单词列表
        
        Args:
            marked_only: 是否只显示标注的单词
            sort_alphabetically: 是否按字母排序
            
        Returns:
            单词列表
        """
        words_query = Word.query
        
        # 如果需要只显示标注单词
        if marked_only:
            words_query = words_query.filter_by(marked=True)
        
        # 如果需要按字母排序
        if sort_alphabetically:
            words_query = words_query.order_by(Word.word)
        
        return words_query.all()

