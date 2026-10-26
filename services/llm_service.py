"""
大语言模型服务层
处理与LLM相关的业务逻辑
"""
import json
import os
import random
import requests
from flask import current_app

from utils.net import describe_error, request as net_request


class LLMService:
    """大语言模型服务类"""
    
    @staticmethod
    def _call_deepseek_api(messages, response_format=None):
        """
        调用DeepSeek API
        
        Args:
            messages: 消息列表
            response_format: 响应格式，可选 {"type": "json_object"}
            
        Returns:
            API响应内容，失败返回None
        """
        try:
            api_key = current_app.config.get('DEEPSEEK_API_KEY')
            base_url = current_app.config.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
            
            if not api_key:
                current_app.logger.error("未配置DEEPSEEK_API_KEY")
                return None
            
            url = f"{base_url}/chat/completions"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            
            data = {
                'model': 'deepseek-chat',
                'messages': messages,
                'temperature': 0.7
            }
            
            if response_format:
                data['response_format'] = response_format
            
            response = net_request('POST', url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            return content
        except requests.exceptions.RequestException as e:
            # 网络层错误单独记一条，方便排查代理/TLS 问题
            current_app.logger.error(f"调用DeepSeek API网络错误: {describe_error(e)}")
            return None
        except Exception as e:
            current_app.logger.error(f"调用DeepSeek API时出错: {str(e)}")
            return None
    
    @staticmethod
    def _get_word_bank(exclude_word='', limit=None):
        """
        取当前词库里的单词，用于"词库联动"提示词。

        规则：星标词优先，其余随机抽样，让每次生成的例句都有变化；
        优先选单词（含空格的短语在例句里很难自然融入），短语只在数量不足时补充。

        Args:
            exclude_word: 要排除的词（正在学习的那个词本身）
            limit: 取多少个，默认读环境变量 WORD_BANK_LIMIT，缺省 40

        Returns:
            单词名列表（可能为空）
        """
        try:
            if limit is None:
                try:
                    limit = int(os.environ.get('WORD_BANK_LIMIT', '40'))
                except ValueError:
                    limit = 40
            if limit <= 0:
                return []

            from models import Word  # 局部导入，避免与 services 包初始化形成循环

            rows = [(w.word, bool(w.marked)) for w in Word.query.all()]
            exclude = (exclude_word or '').strip().lower()

            singles, marked, phrases = [], [], []
            for w, is_marked in rows:
                if not w or w.strip().lower() == exclude:
                    continue
                if ' ' in w.strip():
                    phrases.append(w)
                elif is_marked:
                    marked.append(w)
                else:
                    singles.append(w)

            random.shuffle(marked)
            random.shuffle(singles)
            random.shuffle(phrases)

            bank, seen = [], set()
            for w in marked + singles + phrases:
                key = w.strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                bank.append(w)
                if len(bank) >= limit:
                    break
            return bank
        except Exception as e:
            # 取词库失败不能影响主流程（例如数据库还没准备好）
            try:
                current_app.logger.warning(f"读取词库失败，跳过词库联动: {e}")
            except Exception:
                pass
            return []

    @staticmethod
    def _word_bank_hint(word, limit=None):
        """构造"尽量用词库里的词造句"的提示词片段"""
        bank = LLMService._get_word_bank(word, limit)
        if not bank:
            return ""
        joined = '、'.join(bank)
        return (
            f"\n\n【词库联动】我正在背下面这些单词，请从中挑选 1~2 个与 '{word}' "
            f"语义、场景或搭配相关的词，自然地融进例句里，让我做例句的同时复习自己词表里的词；"
            f"如果实在无法自然融入，就不要硬塞：\n{joined}"
        )

    @staticmethod
    def generate_example(word, part_of_speech, meaning):
        """
        使用DeepSeek API生成例句
        
        Args:
            word: 单词
            part_of_speech: 词性
            meaning: 释义
            
        Returns:
            生成的例句字符串，失败返回None
        """
        if not word or not meaning:
            return None
        
        try:
            hint = LLMService._word_bank_hint(word)
            prompt = f"""请为单词 '{word}' ({part_of_speech}) 生成一个自然、简单易懂且地道的英语例句，
要体现它的含义：'{meaning}'与常用用法。
直接输出句子与这句话的中文意思，不要有任何其它解释。{hint}"""

            messages = [
                {
                    'role': 'system',
                    'content': '你是一个英语学习助手，擅长生成简单易懂的例句。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
            
            example = LLMService._call_deepseek_api(messages)
            
            if example:
                # 简单清理
                example = example.strip()
                example = example.replace('"', '').replace('"', '').replace('"', '')
                if example.startswith("'") and example.endswith("'"):
                    example = example[1:-1]
            
            return example
        except Exception as e:
            current_app.logger.error(f"生成例句时出错: {str(e)}")
            return None
    
    @staticmethod
    def generate_note(word, part_of_speech, meaning):
        """
        使用DeepSeek API生成学习笔记
        
        Args:
            word: 单词
            part_of_speech: 词性
            meaning: 释义
            
        Returns:
            生成的笔记字符串，失败返回None
        """
        if not word or not meaning:
            return None
        
        try:
            hint = LLMService._word_bank_hint(word)
            prompt = f"""请为英语单词 '{word}' ({part_of_speech}) 编写一条学习笔记，含义是：'{meaning}'。
笔记必须按「词根族 / 形近词 / 四级考点」三部分组织，用中文分号「；」连接成一行，
不要换行、不要用列表符号、不要编号，总长 130 字以内：
1. 词根族：列出 2~3 个同词根或同词缀的单词，并点出词根/词缀含义（例：词根 port=搬运 → import/export/transport）
2. 形近词：列出 1~2 个容易混淆的形近词，用括号点出区分点（例：adapt（适应）≠ adopt（采用））
3. 四级考点：说明四级考试中该词的高频搭配、常考词义或典型易错点
示例：词根族：spect(看) → inspect/respect/spectator；形近：expect(期待)≠respect(尊敬)；四级考点：in this respect、with respect to，阅读中常取“方面”义。
只返回这一行笔记内容，不要有标题或任何其他说明。{hint}"""

            messages = [
                {
                    'role': 'system',
                    'content': '你是一个英语学习助手，擅长帮助中国学生记忆英语单词。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
            
            note = LLMService._call_deepseek_api(messages)
            
            if note:
                # 简单清理
                note = note.strip()
                note = note.replace('"', '').replace('"', '').replace('"', '')
                if note.startswith("'") and note.endswith("'"):
                    note = note[1:-1]
            
            return note
        except Exception as e:
            current_app.logger.error(f"生成笔记时出错: {str(e)}")
            return None
    
    @staticmethod
    def generate_full_word_info(word):
        """
        使用DeepSeek API生成完整的单词信息（支持多重释义，同一词性的释义合并）
        
        Args:
            word: 单词
            
        Returns:
            包含完整单词信息的字典，包括多个词性的释义、例句、笔记
            格式：
            {
                "definitions": [
                    {
                        "part_of_speech": "n.",
                        "meaning": "释义1；释义2",
                        "example": "例句1（英文+中文）\n\n例句2（英文+中文）",
                        "note": "学习笔记"
                    },
                    ...
                ]
            }
            或包含错误信息：
            {
                "error": "错误信息"
            }
        """
        if not word:
            return {"error": "单词不能为空"}
        
        try:
            hint = LLMService._word_bank_hint(word)
            prompt = f"""请为英语单词 '{word}' 生成完整的学习信息。

可用的词性列表（共12个）：
- n. (名词)
- v. (动词)
- adj. (形容词)
- adv. (副词)
- prep. (介词)
- conj. (连词)
- pron. (代词)
- interj. (感叹词)
- num. (数词)
- art. (冠词)
- phr. (短语)

要求：
1. 首先验证输入是否为合法的英语单词或短语，如果不是（如中文、数字、乱码等），返回包含error字段的JSON
2. 按词性分组，每个词性一个definition对象
3. 同一词性如果有多个释义，用分号"；"分隔放在meaning字段中
4. 例句格式：英文句子\n中文翻译，自然、简单易懂且地道的英语例句，要体现它的释义含义与常用用法
5. note（学习笔记）字段必须按「词根族 / 形近词 / 四级考点」三部分组织，用中文分号「；」连接成一行，
   不要换行、不要列表符号、不要编号，总长 130 字以内：
   - 词根族：列出 2~3 个同词根或同词缀的单词，并点出词根/词缀含义（例：词根 port=搬运 → import/export/transport）
   - 形近词：列出 1~2 个容易混淆的形近词，用括号点出区分点（例：adapt（适应）≠ adopt（采用））
   - 四级考点：说明四级考试中该词的高频搭配、常考词义或典型易错点
   示例：词根族：spect(看) → inspect/respect/spectator；形近：expect(期待)≠respect(尊敬)；四级考点：in this respect、with respect to，阅读中常取“方面”义。
6. 无论是释义还是词性，排在前面的一定是更常用的
{hint}

7. 必须严格按照以下JSON格式返回：

成功时返回：
{{
    "definitions": [
        {{
            "part_of_speech": "词性（必须从上面12个中选择）",
            "meaning": "释义1；释义2；释义3",
            "example": "英文\\n例句",
            "note": "词根族：...；形近：...；四级考点：..."
        }}
    ]
}}

失败时返回：
{{
    "error": "具体的错误原因"
}}"""

            messages = [
                {
                    'role': 'system',
                    'content': '你是一个专业的英语学习助手，擅长分析单词并生成完整的学习资料。你必须返回有效的JSON格式。请仔细验证输入是否为合法的英语单词。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
            
            # 使用JSON模式
            content = LLMService._call_deepseek_api(
                messages, 
                response_format={"type": "json_object"}
            )
            
            if not content:
                return {"error": "AI服务暂时不可用，请稍后重试"}
            
            # 解析JSON
            result = json.loads(content)
            
            # 检查是否有错误信息
            if 'error' in result:
                return result
            
            # 验证格式
            if 'definitions' not in result or not isinstance(result['definitions'], list):
                current_app.logger.error(f"DeepSeek返回的JSON格式不正确: {content}")
                return {"error": "AI返回格式错误，请重试"}
            
            # 验证definitions不为空
            if len(result['definitions']) == 0:
                return {"error": "未找到该单词的释义，请检查拼写"}
            
            # 确保每个definition都有必需的字段
            for definition in result['definitions']:
                if not all(key in definition for key in ['part_of_speech', 'meaning', 'example', 'note']):
                    current_app.logger.error(f"Definition缺少必需字段: {definition}")
                    return {"error": "AI返回数据不完整，请重试"}
            
            current_app.logger.info(f"成功生成单词 '{word}' 的完整信息，共 {len(result['definitions'])} 个词性")
            return result
            
        except json.JSONDecodeError as e:
            current_app.logger.error(f"解析DeepSeek返回的JSON时出错: {str(e)}, content: {content}")
            return {"error": "AI返回数据解析失败，请重试"}
        except Exception as e:
            current_app.logger.error(f"生成完整单词信息时出错: {str(e)}")
            return {"error": f"生成失败：{str(e)}"}

