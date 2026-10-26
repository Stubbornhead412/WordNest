"""
四级冲刺助教（侧边栏对话）

与 /ai/tutor 的通用 ReAct 助教不同，这里是**面向四级冲刺的固定角色**：
- 角色：基础薄弱大学生的一对一四级辅导老师
- 结合真实单词进度（词库总数 / 星标 / 今天学了什么 / 最近学过什么）
- 覆盖题型：翻译、阅读、写作、语法辨析、短语辨析、易混词辨析
- 每次回答末尾给 1~2 道小练习（含答案）
"""
import json
from datetime import date

import requests
from flask import current_app

from models import Word
from services.ai_service import AIService
from services.notes_service import NotesService
from services.study_service import StudyService

SYSTEM_PROMPT = """你是一位专业的大学英语四级（CET-4）冲刺辅导老师，服务对象是一名英语基础薄弱、正在突击备考四级的大学生。

【教学原则】
1. 客观、理性、务实：先给结论，再给理由；不夸大、不说空话。最多用一行简短鼓励，不要灌鸡汤。
2. 适配基础薄弱的学生：出现语法术语时，先用一句大白话解释，再给术语名称；所有生僻说法都要配中文。
3. 控制篇幅：默认不超过 300 字。用短段落 + 小标题 + 编号，便于手机阅读；不要长篇百科。
4. 所有英文例句都配中文翻译；指出错误时给出「错 → 对」对照。
5. 结合他的真实单词进度（见下方数据），举例时优先用他词库里的词；绝对不要编造他"学过"的词。
6. 如果他问的东西超纲或无关，直接说明并拉回四级范围。
7. 下方附有他的【手写笔记】。这是他亲手记的内容，优先级很高：
   - 他问"我笔记里写了什么"时，直接引用，不要改写意思
   - 可以主动用笔记里记的错误、易混点、薄弱环节来出题或提醒
   - 但严禁编造笔记里没有的内容；笔记为空时就当作没有

【你擅长的训练】
- 翻译：汉译英 / 英译汉，含四级常考句式、提示词、评分要点
- 阅读：主旨题、细节题、词义猜测、长难句拆解（先切分主干再翻译）
- 写作：三段式结构、常用连接词、替换词、常见扣分点
- 语法辨析：时态、非谓语、主谓一致、从句、虚拟语气、被动语态
- 短语辨析：固定搭配、介词搭配、形似短语
- 易混词辨析：形近词、义近词、同词根词（用一句话点出区分点）

【输出规范】
- 除用户明确说"不要练习"外，每次回答的最后加一段「**小练习**」：1~2 题，紧跟本轮内容，并在题后直接给「答案 + 一句解析」。
- 若用户问"怎么提分 / 怎么安排时间"，给出今天就能执行的最小行动（做什么、做多久、做几题）。
- 需要时可用 Markdown（**加粗**、`代码`、短列表），但不要用大标题。

"""

WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


class CET4Coach:
    """四级冲刺助教服务"""

    @staticmethod
    def build_progress_context():
        """
        汇总学员真实进度，拼成一段可以直接塞进 system prompt 的文本。
        取数失败时返回中性说明，不影响对话。
        """
        lines = ['【学员当前进度（来自系统真实数据）】']
        try:
            total = Word.query.count()
            marked_words = Word.query.filter_by(marked=True).all()
            lines.append(f'- 词库总词数：{total}')
            lines.append(f'- 已星标（重点攻克）：{len(marked_words)}')

            marked_names = '、'.join(w.word for w in marked_words[:12])
            if marked_names:
                lines.append(f'- 星标词示例：{marked_names}')

            today = date.today()
            today_words = StudyService.word_texts_for_day(today.strftime('%Y-%m-%d'))
            weekday = WEEKDAYS[today.weekday()]
            if today_words:
                preview = '、'.join(today_words[:15])
                lines.append(f'- 今天（{today.strftime("%m-%d")} {weekday}）已学 {len(today_words)} 词：{preview}')
            else:
                lines.append(f'- 今天（{today.strftime("%m-%d")} {weekday}）还没有学习记录')

            summary = StudyService.summary()
            lines.append(
                f'- 近 7 天学习 {summary.get("week", 0)} 词，累计去重 {summary.get("total_words", 0)} 词，'
                f'学习天数 {summary.get("total_days", 0)} 天'
            )

            days = StudyService.days_with_words(3)
            if days:
                brief = '；'.join(f'{d["label"]} {d["count"]} 词' for d in days)
                lines.append(f'- 最近几天：{brief}')

            # 顺手给几个"最近学过的词"，方便出练习时取材
            if days and days[0].get('words'):
                recent = '、'.join(w['word'] for w in days[0]['words'][:10])
                if recent:
                    lines.append(f'- 今天学过的词（可优先用于造句/练习）：{recent}')
        except Exception as e:
            try:
                current_app.logger.warning(f'读取学习进度失败，使用中性上下文: {e}')
            except Exception:
                pass
            lines.append('- （当前无法读取进度数据，按普通学员处理）')

        # 手写笔记：作为他最重要的私人参考
        try:
            notes_text, notes_count = NotesService.recent_for_ai(limit=8, max_chars=220)
            lines.append('')
            lines.append('【学员的手写笔记（他自己记的，优先参考）】')
            if notes_count and notes_text:
                lines.append(f'共 {notes_count} 条，最近 {min(8, notes_count)} 条：')
                for line in notes_text.split('\n'):
                    if line.strip():
                        lines.append('  ' + line.strip())
            else:
                lines.append('- 目前还没有手写笔记')
        except Exception as e:
            try:
                current_app.logger.warning(f'读取笔记失败，跳过: {e}')
            except Exception:
                pass
            lines.append('- （笔记暂时读取不到）')

        lines.append('出题时优先使用上面出现的单词，但不要曲解它们的含义。')
        return '\n'.join(lines)

    @staticmethod
    def stream(message, history=None):
        """
        流式回答（SSE，与 /ai/chat_stream 的格式一致：data: {"content": "..."}）

        Args:
            message: 用户消息
            history: [{"role": "user"|"assistant", "content": "..."}]，最多取最近 8 条
        """
        try:
            progress = CET4Coach.build_progress_context()
            messages = [{'role': 'system', 'content': SYSTEM_PROMPT + '\n' + progress}]

            for item in (history or [])[-8:]:
                role = item.get('role')
                content = (item.get('content') or '').strip()
                if role in ('user', 'assistant') and content:
                    messages.append({'role': role, 'content': content[:2000]})

            messages.append({'role': 'user', 'content': message})

            response = AIService.call_llm(messages, stream=True)

            for line in response.iter_lines():
                if not line:
                    continue
                text = line.decode('utf-8', 'replace')
                if not text.startswith('data: '):
                    continue
                payload = text[6:].strip()
                if payload == '[DONE]':
                    yield 'data: [DONE]\n\n'
                    break
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = data.get('choices') or []
                if not choices:
                    continue
                delta = choices[0].get('delta') or {}
                content = delta.get('content') or ''
                if content:
                    yield 'data: ' + json.dumps({'content': content}, ensure_ascii=False) + '\n\n'

        except ValueError as e:
            # 通常是没配 API Key
            msg = str(e)
            if 'DEEPSEEK_API_KEY' in msg:
                msg = '还没有配置 DeepSeek API Key，请在项目的 .env 里填写 DEEPSEEK_API_KEY 后执行 docker compose up -d'
            yield 'data: ' + json.dumps({'content': '⚠️ ' + msg}, ensure_ascii=False) + '\n\n'
            yield 'data: [DONE]\n\n'
        except requests.exceptions.RequestException as e:
            # 网络类问题（TLS 被拦、代理没开、超时）统一给一句人话，别把堆栈丢给用户
            from utils.net import describe_error
            msg = describe_error(e)
            try:
                current_app.logger.error(f'四级助教网络错误: {msg} | {e}')
            except Exception:
                pass
            yield 'data: ' + json.dumps({'content': '⚠️ ' + msg}, ensure_ascii=False) + '\n\n'
            yield 'data: [DONE]\n\n'
        except Exception as e:
            try:
                current_app.logger.error(f'四级助教流式回答失败: {e}')
            except Exception:
                pass
            yield 'data: ' + json.dumps({'content': f'❌ 出错了：{e}'}, ensure_ascii=False) + '\n\n'
            yield 'data: [DONE]\n\n'
