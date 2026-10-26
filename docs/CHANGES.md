# 改动清单（相对上游 WordNest）

> 本项目是 [wink-wink-wink555/WordNest](https://github.com/wink-wink-wink555/WordNest) 的二次开发版。
> 本文按「新增 / 修复 / 功能 / 移除 / 数据」分类列全所有改动，方便对照上游代码 review。
>
> 部署与使用说明见 [DOCKER.md](DOCKER.md)；项目介绍见 [../README.md](../README.md)。

---

## 一、部署与运行环境（全部新增）

| 文件 | 内容 | 为什么需要 |
| --- | --- | --- |
| `Dockerfile` | `python:3.11-slim` + `espeak-ng`（朗读）+ `gunicorn`；apt 换阿里云、pip 换清华源 | 上游没有容器化，国内直连 Debian/PyPI 会超时 |
| `docker-compose.yml` | 端口映射、4 个数据目录挂载、健康检查、环境变量、`host.docker.internal` 映射 | 一条命令启动；数据落在宿主机，重建容器不丢 |
| `.dockerignore` | 排除数据目录、截图、`.git` | 构建上下文从 ~10 MB 降到几百 KB |
| `.env.example` | Key / 端口 / 词库抽样数 / 时区 / 访问密码模板 | `.env` 里有密钥，不能提交，靠模板生成 |
| `.devcontainer/devcontainer.json` | VSCode 一键进容器，F5 直接调试 | 不装 Python 也能改代码 |
| `.vscode/tasks.json`、`launch.json`、`extensions.json`、`settings.json` | `docker: 启动/重建/看日志/进容器` 任务，调试配置，推荐扩展 | 常用操作不用记命令 |
| `start-wordnest.ps1` | 一键启动（含 Docker 未启动时自动拉起） | 双击就能用 |
| `start-tunnel.ps1` | 启动 Cloudflare 快速隧道，把本机 5000 暴露成公网 HTTPS 地址 | 手机在外网也能刷词 |
| `.gitattributes` | 统一 LF、二进制文件不转换 | Windows 上避免 CRLF 进仓库导致脚本/Docker 出问题 |

---

## 二、修复上游问题

| 文件 | 改动 | 上游的问题 |
| --- | --- | --- |
| `requirements.txt` | 补 `requests` | **上游漏依赖**，容器启动直接 `ModuleNotFoundError: No module named 'requests'` |
| `requirements.txt` | 补 `flask-compress` | 列表页未压缩 540 KB，手机打开很慢；压缩后 102 KB |
| `routes/word_routes.py` | `/speak_word` 返回 `.wav` + `audio/wav` | pyttsx3 生成的是 WAV，原代码标成 `audio/mpeg`，部分浏览器放不出声 |
| `app.py` | 切换词表时只替换默认引擎，不清空 chat/study 引擎 | 原代码 `db.engines.clear()` 会连带清掉 chat/study 绑定，切列表后 AI 对话/学习记录报错 |
| `app.py` | SQLite pragma：只为轮转库设 `MEMORY` 日志 | 数据目录挂在 Windows（9p），**不支持 WAL 共享内存**，开 WAL 后新连接打不开库（表现为词数变 0、进度条不动） |
| `services/ai_service.py`、`graph_service.py`、`llm_service.py` | 出网统一走 `utils/net.py` | 开 Clash 后容器内 TLS 被掐，AI 报 `SSL: UNEXPECTED_EOF` |
| `utils/net.py` | **新增**：先代理后直连、超时重试、错误归类 | 让 AI 在「开代理/关代理」两种状态下都能用 |

---

## 三、新增功能

| 功能 | 涉及文件 | 说明 |
| --- | --- | --- |
| **每日学习记录** | `models.py`（`StudyRecord`）、`services/study_service.py`、`routes/study_routes.py`、`templates/study_log.html`、`index.html`/`word_list.html` 入口 | 按天记录学过的词，30 天柱状图，可一键复习某天的词 |
| **学习笔记** | `models.py`（`Note`）、`services/notes_service.py`、`routes/notes_routes.py`、`templates/notes.html`、`cet4_coach.py` 注入 | 多条笔记、可关联单词、可搜索；AI 会读最近 8 条当参考 |
| **四级冲刺助教侧栏** | `services/cet4_coach.py`、`templates/_ai_panel.html`、`static/ai_panel.js`、`routes/ai_routes.py`（`/ai/coach_stream`、`/ai/quick_words`） | 左侧可拖宽面板，按真实单词进度出题答疑，含快速选词复制；窄屏自动收起 |
| **词库联动例句** | `services/llm_service.py`（`_word_bank_hint` / `_get_word_bank`）、`docker-compose.yml` 的 `WORD_BANK_LIMIT` | AI 造句时优先复用你词表里的词（星标优先，默认抽 40 个） |
| **按轮抽词算法** | `services/cycle_service.py`、`models.py`（`WordCycleMeta`/`WordCycleServed`）、`services/word_service.py`、`routes/word_routes.py`、`routes/study_routes.py` | 一轮内不重复、词库随时增删不错位、跨设备/重启接续；替代原来"每次随机+只排除上一个词" |
| **本轮进度显示** | `templates/index.html`（进度条）、`static/script.js`（更新逻辑）、`routes/word_routes.py`（`/get_cycle_progress`） | 自测页底部显示「本轮 37 / 400」，悬停显示还剩多少 |
| **可选访问密码** | `config.py`（`ACCESS_PASSWORD`）、`utils/auth.py`、`routes/auth_routes.py`、`templates/login.html`、`app.py`（`check_access`） | 手机/公网访问前建议开启；不配置则和上游一样无需登录 |
| **CSV 导入 / 批量补例句** | `import_vocabulary.py`、`enrich_words.py`、`vocabulary.sample.csv` | 导入自己的词表（`--csv/--list/--replace`），批量让 AI 补例句和记忆法（支持断点续跑） |
| **手机端适配** | `static/style.css`（`@media` 覆盖）、`templates/_ai_panel.html` | 长单词不再压住图标按钮，侧栏自动收起 |
| **新蓝图注册** | `routes/__init__.py` | 把 `auth`、`notes`、`study` 三个新蓝图注册到应用；不加这行新页面路由不生效 |

---

## 四、移除 / 调整的行为

| 项目 | 改动 | 原因 |
| --- | --- | --- |
| 全局键盘快捷键 | 移除空格＝看释义、`→`＝下一个、`←`＝上一个、`↓`＝看意思 | 输入框打字时空格会误触，释义闪来闪去 |
| `README.fr.md` | 删除 | 法文版本项目读者用不到 |
| `README.md` / `README.en.md` | 顶部新增「关于本仓库（二次开发版）」+ 改动概览；语言切换去掉法文 | 符合 MIT 的署名要求，也让访客一眼知道改了什么 |
| `README.docker.md` | 改名移动到 `docs/DOCKER.md` | 部署手册很长，不该占根目录 |
| `docs/CHANGES.md` | **新增（本文件）** | 把"改了哪些文件、为什么改、怎么验证"集中记录，避免散落在章节里 |
| `import_vocabulary.py` | 从"写死路径的一次性脚本"改成通用 CLI | 原版写死 `C:\Users\Asus\...`，别人拿到跑不了 |
| `enrich_words.py` | 同上，支持 `--list/--base-url/--db` | 同上 |

---

## 五、数据文件（都不进仓库）

| 文件 | 内容 | 是否可丢 |
| --- | --- | --- |
| `instance/words.db` | 词表（每个词表一个 `.db`） | ❌ 不可丢 |
| `instance/demo.db` | 上游示例词表（21 词） | 可丢 |
| `study_data/study.db` | 学习记录 + 笔记 | ❌ 不可丢 |
| `study_data/cycle.db` | 本轮抽词状态 | ✅ 可丢（删了重新开一轮） |
| `chat_data/chat.db` | AI 对话记录 | 可丢 |
| `settings.json` | 界面偏好 | 可丢 |

`.gitignore` 排除了以上全部，以及 `.env`、`backup/`、`screenshot_*.png`。

---

## 六、验证记录（实测，非估算）

| 项目 | 结果 |
| --- | --- |
| 容器启动 | `Up (healthy)`，`/`、`/word_list`、`/notes`、`/study_log` 均 200 |
| 抽词一轮 | 400 次抽取覆盖 400 个词、零重复；中途新增 3 词 → 该轮变 403 且新词都出现 |
| 跨设备/重启 | 新客户端无重叠；重启容器后 `served` 从 36 连续到 37 |
| 抽词延迟 | 456 ms → **34 ms**（中位），P90 58 ms |
| 列表页体积 | 540 KB → **102 KB**（gzip） |
| 完整"陌生人"流程 | 全新目录、无 `.env` 可直接启动；导入示例 CSV 得 20 词；未填 Key 时 AI 提示友好；填 Key 后 AI 正常回答 |
