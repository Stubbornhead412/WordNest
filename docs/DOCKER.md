# WordNest × Docker Desktop × VSCode 部署说明

> 本文档位于 docs/DOCKER.md，项目根目录见 [README.md](../README.md)。

本目录是 [wink-wink-wink555/WordNest](https://github.com/wink-wink-wink555/WordNest) 的二次开发版，
补好了在 **Docker Desktop + VSCode** 下运行所需的全部配置。

- 镜像：`wordnest:local`　容器：`wordnest`　地址：<http://localhost:5000>
- 数据：`instance/`（词库）、`study_data/`（学习记录+笔记）、`chat_data/`（AI 对话）都挂载到宿主机，**重建容器不丢数据**

---

## 零、快速开始（3 步）

### 需要什么环境

| 必需 | 说明 |
| --- | --- |
| **Docker Desktop**（Windows / macOS）或 Docker Engine + Compose（Linux） | 唯一硬性要求。Windows 建议开启 WSL2 后端 |
| 浏览器 | Chrome / Edge / Safari 都行；手机浏览器也可以 |

| 可选 | 什么时候需要 |
| --- | --- |
| **Python 3.8+** | 只有跑 `import_vocabulary.py`（导入词表 CSV）、`enrich_words.py`（AI 批量补例句）才需要；两个脚本只用标准库，不用 pip 安装 |
| **VSCode + Dev Containers 扩展** | 想按 F5 调试、或不想装 Python 时用（容器里什么都装好了） |
| **DeepSeek API Key** | 想用 AI（例句/记忆法/知识图谱/助教）才需要；不填也能正常背单词 |

> 也就是说：**装了 Docker Desktop，解压就能跑，不需要 Python、不需要 Node、不需要数据库。**

### 第 1 步：启动

```powershell
cd WordNest
docker compose up -d --build      # 第一次会构建镜像，约 1~2 分钟
```

浏览器打开 <http://localhost:5000> —— 此时是空词表，可以手动加词、背单词、看学习记录，只是 AI 不可用。

> 不用先创建 `.env`：`docker-compose.yml` 里所有配置都有默认值，没 `.env` 也能启动。

### 第 2 步（可选）：填 API Key，让 AI 可用

```powershell
# 复制模板
copy .env.example .env        # macOS/Linux: cp .env.example .env

# 编辑 .env，填一行（Key 从 https://platform.deepseek.com/api_keys 申请）
#   DEEPSEEK_API_KEY=sk-你的密钥

docker compose up -d          # 让容器读到新配置（不需要 --build）
```

验证：进「添加单词」页点 **AI 一键填充**，或点左下角 AI 助教问一句。

> 没填 Key 时点 AI 会提示「还没有配置 DeepSeek API Key」——这是预期行为，其它功能不受影响。

### 第 3 步（可选）：导入自己的词表

准备一个 CSV（UTF-8，带表头），最少要有「单词」和「释义」两列：

```csv
序号,单词/短语,音标,词性,中文释义,类型,首字母
1,abuse,əˈbjuːs,n./v.,滥用；虐待；辱骂,单词,a
2,academy,əˈkædəmi,n.,学院；研究院；专科院校,单词,a
```

```powershell
docker compose stop                                    # 先停容器，避免数据库写入竞争
python import_vocabulary.py --csv vocabulary.csv       # 导入到默认词表 words
docker compose start
```

- 想导成**独立词表**（不动原有数据）：`--list cet4`
- 目标词表已有词、想覆盖：加 `--replace`（会自动备份到 `backup/`）
- 想先试试效果：仓库里带了一份 **`vocabulary.sample.csv`（20 个四级词）**，可以直接导入
- 没有 Python？把 CSV 放到项目目录后，用容器执行：
  `docker compose run --rm -v "%cd%:/app" --entrypoint python wordnest import_vocabulary.py --csv vocabulary.csv`

导入完成后刷新网页，右上角能看到词表；想让 AI 批量补例句/记忆法：

```powershell
python enrich_words.py --limit 10 --dry-run    # 先预览 10 个
python enrich_words.py --limit 0               # 全量补齐
```

---

## 一、最常用的三种启动方式

### 方式 1：VSCode 任务（最省事）

1. 打开 Docker Desktop，等鲸鱼图标变成绿色（引擎就绪）。
2. VSCode 打开本文件夹（`文件 → 打开文件夹` → 选 `WordNest`）。
3. `Ctrl+Shift+P` → 输入 `Run Task` → 选 **`docker: 启动 WordNest (build + up)`**。
4. 再运行任务 **`打开 http://localhost:5000`**，或直接浏览器访问。

其他任务：`docker: 查看日志`、`docker: 状态 / 端口`、`docker: 重启`、`docker: 停止 (保留数据)`、`docker: 进入容器 shell`。

### 方式 2：Dev Container（推荐用来改代码 / 断点调试）

1. VSCode 安装扩展 **Dev Containers**（打开文件夹时会自动提示推荐扩展）。
2. `F1` → **Dev Containers: Reopen in Container**（首次会构建镜像，之后秒开）。
3. 容器里按 **F5**，选择 `WordNest: Flask 调试 (端口 5000)`，即可在 `/app` 里带断点调试，
   浏览器访问 <http://localhost:5000>（端口自动转发）。

容器内代码是挂载的宿主机目录，改完保存后在容器里重启调试即可生效。

### 方式 3：命令行 / 一键脚本

```powershell
# 在 WordNest 目录下
.\start-wordnest.ps1          # 自动启动 Docker Desktop + 构建 + 启动 + 打开浏览器

# 或者直接
docker compose up -d --build  # 构建并后台启动
docker compose logs -f        # 看日志
docker compose down           # 停止（保留 instance/ 等数据）
```

> `start-wordnest.ps1` 若被系统策略拦截，用：
> `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-wordnest.ps1`

---

## 二、配置 AI 功能（DeepSeek）

不配也能正常背单词：**手动加生词、随机抽查、星标、词表管理、CSV 导出、朗读发音全部可用**。
只有「AI 生成例句 / 记忆法 / 知识图谱 / AI 助教」需要 API Key。

1. 到 <https://platform.deepseek.com/api_keys> 申请 Key。
2. 打开本目录的 `.env`，填上：

   ```ini
   DEEPSEEK_API_KEY=sk-你的密钥
   ```

3. 让容器读到新配置：

   ```powershell
   docker compose up -d
   ```

4. 进「添加单词」页，点 AI 一键填充试试。

> ⚠️ 上游 `config.py` 里 `DEEPSEEK_BASE_URL` 的默认值结尾多了两个空格
> （`'https://api.deepseek.com  '`），会让 `requests` 拼出非法 URL。
> 本项目的 `.env` 已显式写成 `https://api.deepseek.com`，**不要删掉这一行**。

### 出网代理（重要，开了 Clash 才需要管）

宿主机开着 **Clash / Clash Verge / v2ray** 这类代理（尤其是 **TUN 模式**或系统代理）时，
WSL 里容器的直连 TLS 会被掐断，AI 会报：

```
SSL: UNEXPECTED_EOF_WHILE_READING / The handshake operation timed out
```

原因是代理接管了宿主机的流量，但没接管 Docker 容器的网络。项目已经做了自动处理：
**先走宿主机代理端口，失败再回落直连**，所以在"开代理"和"关代理"两种状态下都能用。

代理端口写在 `.env`：

```ini
WORDNEST_PROXY=http://host.docker.internal:7897
```

- Clash Verge 默认混合端口是 `7897`；Clash for Windows 常见是 `7890`
- 不确定端口：看代理软件设置里的"混合端口 / Mixed Port"
- 想完全不走代理：把这一行留空
- 代理没开时不会报错，会自动直连（连接被拒是瞬时的）

---

## 三、相对上游的增强

**新增功能、优化项与使用方法见 [FEATURES.md](FEATURES.md)。**

本版本在上游「Flask 单机版」的基础上，补充的是**跑起来、用得顺、随身可用**这一层：

| 分类 | 主要内容 |
| --- | --- |
| 部署 | `Dockerfile`、`docker-compose.yml`、`.env.example`、`.dockerignore`、`.devcontainer`、`.vscode`、`start-wordnest.ps1` |
| 修复上游问题 | `requirements.txt` 补 `requests`（否则启动即崩）、`/speak_word` 音频类型、切换词表清空引擎、SQLite 在 9p 挂载下的兼容 |
| 新功能 | 每日学习记录、学习笔记、四级助教侧栏、词库联动例句、按轮抽词算法 + 进度条、可选访问密码、CSV 导入与批量补例句 |
| 移除 | 全局键盘快捷键（空格/方向键误触） |
| 文档整理 | 二次开发署名、部署手册移入 `docs/`、删除法文 README |

### 数据库分布与性能说明

Docker Desktop 把 Windows 目录以 **9p/drvfs** 挂载进容器，该文件系统不支持 SQLite 的 WAL 共享内存，
因此项目按用途拆分数据库并使用不同的日志模式：

| 数据库 | 位置 | 日志模式 | 说明 |
| --- | --- | --- | --- |
| `words.db` / `demo.db` | `instance/` | 默认（delete） | 词库，优先保证安全 |
| `study.db` | `study_data/` | 默认（delete） | 学习记录 + 笔记，优先保证安全 |
| `chat.db` | `chat_data/` | 默认（delete） | AI 对话记录 |
| `cycle.db` | `study_data/` | **MEMORY + synchronous=OFF** | 只存"本轮抽过哪些词"，可丢弃，写入约 4 ms |

`cycle.db` 丢失只会让本轮重新开始、可能重复出现几个词，不影响词库与笔记；
删除该文件即可手动重置轮次。备份时只需保留 `instance/`、`study_data/study.db`、`chat_data/`。

### 抽词算法（与词数无关，词库随时增删都正确）

以前是"每次从全库随机 + 只排除上一个词"。按生日问题，400 词里
**20 次抽取内出现重复的概率约 39%**，10 次也有约 11%，所以会觉得"刚看过又来了"。

现在改成**按轮发牌，但记录的是"这一轮发过哪些词"，而不是"排到第几张"**：

- 每轮一个随机 `seed`；取词时在"本轮还没发过的词"里按 `sha1(seed|word)` 排序取第一张
  → 顺序看起来是乱序，但**一轮内绝不重复**
- **新增单词**：它在"已发集合"里没有记录 → **立刻进入本轮候选**，不用等下一轮
- **删除单词**：记录残留无害，取词时只按当前词库过滤
- **换浏览器/手机**：状态在数据库（`study_data/study.db`），接力继续同一轮，不会重新洗牌
- **重启容器**：状态不丢，继续上一轮
- **跨轮衔接**：新一轮第一张不会等于上一轮最后一张
- 不同池子独立计数：全部单词 / 只看星标 / 复习某一天

> 这个设计的关键点：不依赖"排序位置"，所以词数从 400 变成 40000、或者中途加词删词，
> 都不会出现"跳过某些词"或"重复某些词"的问题。

接口 `GET /get_random_word` 会顺带返回本轮进度，例如：

```json
{"word": "forbid", "progress": {"cycle": 1, "served": 1, "total": 400}}
```

**页面上也显示出来了**：自测页鼓励语下面有一行「本轮 ▁▁▁ 7 / 400」，
进度条按 `served/total` 变化，鼠标悬停显示「第 1 轮：已抽 7 个，还剩 393 个」。

- 每次点「下一个」自动更新
- 刷新页面不会重新开始（进度存在数据库里），加载时用 `GET /get_cycle_progress` 拉一次
- 切换「仅抽查星标」或进入「复习某一天」时，进度条显示的是对应池子的进度
- 没有可抽的词（列表为空）时自动隐藏

> 实测（真实 HTTP 请求）：
> 连续 60 次 → 60 个不同词；跑满一轮 400 次 → 400 词全覆盖零重复；
> **本轮中途新增 3 个词 → 这一轮长度变成 403，且新词都在本轮出现**；
> 删除一个未出现的词 → 不报错、不重复；换客户端 → 无重叠；重启容器 → `served` 从 36 连续到 37。
> 页面进度：加载显示 `2 / 400`，点一次变 `3 / 400`，连点 4 次变 `7 / 400`（桌面与手机尺寸均正常）。

---

## 四、导入自己的单词表（CSV）

CSV 需要的列（顺序无所谓，按表头识别；最少要有「单词」和「释义」）：
`序号,单词/短语,音标,词性,中文释义,类型,首字母`

导入脚本：[import_vocabulary.py](../import_vocabulary.py)（已改成通用 CLI，路径不再写死）

```powershell
# 1) 先停容器，避免 SQLite 写入竞争
docker compose stop

# 2) 导入（默认读项目根目录的 vocabulary.csv，导入到 words 词表）
python import_vocabulary.py --csv vocabulary.csv

# 3) 启动
docker compose start
```

常用参数：

| 参数 | 作用 |
| --- | --- |
| `--csv <路径>` | 指定 CSV（默认 `vocabulary.csv`） |
| `--list <名字>` | 导入到哪个词表（默认 `words`；填 `cet4` 就是新建一个词表，**不动原有数据**） |
| `--replace` | 目标词表已有单词时，先备份再清空导入（不加这个参数会拒绝覆盖，防止误操作） |

新手可以直接用仓库自带的 **`vocabulary.sample.csv`（20 个四级词）** 试手：

```powershell
python import_vocabulary.py --csv vocabulary.sample.csv --list demo20
```

规则说明：

- **音标**项目里没有独立字段，脚本会写进「笔记」字段，形如 `音标 /əˈbjuːs/`，卡片上能直接看到。
- **例句**留空，用 AI 一键填充即可补上（见下节）。
- 重复词自动跳过，含空格的短语也能导入。
- 导入前自动备份到 `backup/<词表>.db.<时间戳>.bak`，回滚拷回去即可。
- 没有 Python 也能导：`docker compose run --rm -v "%cd%:/app" --entrypoint python wordnest import_vocabulary.py --csv vocabulary.csv`

---

## 五、AI 造句复用你的词表（词库联动）

每次调用 AI 生成例句 / 记忆法时，服务端会从当前词表里**随机抽 40 个词**（星标词优先）塞进提示词，
要求模型挑 1~2 个语义相关的词自然融进句子，**让你在例句里复习自己刚背过的词**。

实测效果：

```
academy  →  She was invited to give a lecture at the academy about the crucial role of
            discipline in scientific research.
            （复用了词表里的 crucial、discipline）

ephemeral → The distinction between the two species is ephemeral and partly due to
            seasonal changes.   （复用了 distinction、partly、species）
```

调节方式（改 `.env` 后 `docker compose up -d`）：

| 配置 | 效果 |
| --- | --- |
| `WORD_BANK_LIMIT=40` | 默认，每次抽 40 个词 |
| `WORD_BANK_LIMIT=80` | 抽更多词，复用概率更高，但提示词更长 |
| `WORD_BANK_LIMIT=0` | 关闭词库联动，恢复成原来的"纯生成" |

### 顺手批量补例句 / 记忆法

导入时例句默认为空，可以用脚本一次性补齐（走项目自己的 AI 接口，只改
`example` / `note`，**不动** CSV 里的词性和中文释义，音标会自动保留在笔记末尾）：

```powershell
python enrich_words.py --limit 6 --dry-run   # 先预览 6 个，不写库
python enrich_words.py --limit 6             # 真写 6 个
python enrich_words.py --limit 0             # 全量（0 = 全部；可反复跑，已补过自动跳过）
```

速度约 2.3 秒/词，400 词约 15 分钟；中途断掉重跑即可续上。

**笔记格式**已按背单词需求改成三段式（约 130 字，用「；」连接）：

```
词根族：tribut(给予) → contribute/distribute/attribute；形近：contribute(贡献)≠attribute(归因)；
四级考点：attribute A to B 是高频搭配，阅读中常考"归因于"义。（音标 /əˈtrɪbjuːt/）
```

- **词根族**：2~3 个同词根/同词缀的单词，帮你成串记
- **形近词**：1~2 个易混词，括号里写区分点
- **四级考点**：常考搭配、常考词义、易错点


---

## 六、每日学习记录（按天复习）

自动记录"今天学过哪些单词"，并按天汇总成可回看的目录 + 时间序列图。

**入口**：自测页右上角「学习记录」/ 词表工具栏「学习记录」/ 直接访问 <http://localhost:5000/study_log>

**记录规则**（全自动，不用手动打卡）：

| 动作 | 是否记录 |
| --- | --- |
| 自测页点「查看意思」、打开单词详情 | ✅ 记一次 |
| 星标 / 取消星标 | ✅ 记一次 |
| 同一词同一天反复看 | 只算 1 个词，次数累加（页面上显示 `×N`） |
| 只是切换单词、不看释义 | ❌ 不记录 |

**页面内容**：

- **4 个统计卡**：今天 / 近 7 天 / 累计去重词数 / 学习天数
- **近 30 天柱状图**：黄色为今天，点柱子直接跳到那一天的目录
- **按天目录**：点开某一天，列出当天所有单词（词性 + 释义 + 星标 + 次数），每行末尾有「复习这 N 个词」
- **复习模式**：点按钮后回到自测页，抽查范围只剩当天的词，页面顶部有绿色提示条，点 ✕ 退出
- **深链**：`/study_log#day-2026-10-20` 可直接展开某一天

**数据位置**：`study_data/study.db`（独立数据库，切换单词列表不影响统计；已挂载到宿主机）。

> 实现注意：session 里只存复习的**日期**而不是整份词表——Flask 默认把 session 放在 Cookie 里，上限 4KB，
> 存几百个单词会静默失效；现在 Cookie 只有约 100 字节。

---

## 七、左侧「四级冲刺助教」侧栏

自测页 / 词表页 / 学习记录页的**左侧**都有一条常驻 AI 对话栏，人设是"基础薄弱大学生的一对一四级辅导老师"。

**打开方式**：默认展开（状态记在浏览器 localStorage）。点右上的 `‹` 收起，收起后左侧留一个竖排「AI 四级助教」按钮，再点展开。

**它会结合你的真实进度**（每次提问自动带上）：词库总词数、星标重点词、今天学了哪些词、近 7 天学习量、最近几天的记录。
所以可以直接问"用我今天学的词出 3 道题"，它会用 `talented`、`agency` 这类你真的在背的词。

**教学设定**（写在 `services/cet4_coach.py` 的 SYSTEM_PROMPT 里，可自行改）：

- 客观理性、结论先行，不灌鸡汤；出现语法术语先用大白话解释
- 覆盖题型：翻译、阅读（主旨/细节/词义猜测/长难句拆解）、写作模板、语法辨析、短语辨析、易混词辨析
- 所有英文例句配中文；纠错用「错 → 对」对照
- 每次回答末尾自动加 **小练习**（1~2 题 + 答案 + 一句解析）
- 默认控制在 300 字以内，适合手机阅读

**快捷按钮**：翻译练习 / 语法辨析 / 易混词 / 短语辨析 / 阅读长难句 / 写作模板 / 我的进度 —— 点一下就直接发对应提示词。

**快速选词复制**（在输入框上方）：

- 「今天学的」和「星标词」两个页签，显示你真实学过的词
- **单击词块 = 复制到剪贴板**（失败时自动降级到 execCommand，并在底部弹出「已复制 xxx」提示）
- **双击词块 = 填入输入框**，接着打字提问
- 「复制全部」= 把当前页签的单词用英文逗号拼接后一次复制（方便贴到别的工具里）

**调整宽度**（三种方式，宽度记在 localStorage，下次打开还是这个宽度）：

| 操作 | 效果 |
| --- | --- |
| 拖动侧栏**右边缘**的竖条 | 随意加宽 / 收窄（300 ~ 视口宽度-280） |
| 双击该竖条 | 还原默认宽度 |
| 点标题栏 `⤢` | 一键在「加宽 620px」和「默认宽度」之间切换 |

正文会自动让位（`body` 左内边距跟着变），不会遮住内容；窗口宽度 < 1200px 时自动变成底部浮层，拖拽把手隐藏。

**同步单词列表（不丢对话）**：

右侧刷词时，侧栏的「今天学的」列表会自动跟上——因为侧栏监听了一次 `fetch`，
只要你触发了 `/get_word_definition/`（点「查看意思」）、`/mark_word/` 或 `/unmark_word/`，
就会在 0.4 秒后静默重新拉取词表。

也可以手动点词语区右侧的 **`↻ 同步`**：
- 有新词 → 底部提示「已同步：今天 N 词 / 星标 M 词」，词语区右侧绿点亮一下
- 没有新词 → 提示「已是最新，没有新单词」
- **对话完全不受影响**（同步只重绘词语区，不碰消息列表）

此外切回浏览器标签页、窗口获得焦点、AI 回答结束时，也会各自动同步一次。
注意：AI 每次回答用的进度数据本来就是**实时从数据库查的**，所以即使不点同步，提问时它也知道你今天新学了什么；同步按钮只影响你眼前看到的词块列表。

**接口**：`POST /ai/coach_stream`（SSE 流式）、`GET /ai/quick_words`（侧栏选词数据）。
对话历史存在浏览器 sessionStorage（刷新不丢、换标签页重新开始），不会写库。

---

## 八、学习笔记（AI 会参考）

背单词过程中随手记事：哪个词老混、老师怎么讲、阅读/作文的套路，都可以记，**AI 助教会把这些笔记当作参考资料**。

**入口**：

| 位置 | 行为 |
| --- | --- |
| 自测页右上角「我的笔记」 | 打开笔记页 |
| **单词卡上的笔记图标**（🔊 ✎ ⭐ 旁边） | 打开笔记页并**自动关联当前单词**（`/notes?word=xxx`） |
| 词表页工具栏「笔记」 | 打开笔记页 |
| 学习记录页导航「我的笔记」 | 打开笔记页 |
| 直接访问 | <http://localhost:5000/notes> |

**功能**：

- **多条笔记**：左侧列表按更新时间倒序，右侧编辑；点列表项即切换
- **字段**：标题（可空）、关联单词（可空）、标签（可空，逗号分隔）、正文
- **搜索**：标题 / 正文 / 关联单词 / 标签，全部匹配（输入即搜，300ms 防抖）
- **快捷键**：`Ctrl+S`（macOS `Cmd+S`）保存
- **删除**：选中笔记后点「删除这条」，二次确认
- **自动标题**：不写标题也行，列表会显示正文前 70 字
- 深色模式适配、窄屏自动单列

**AI 如何"看到"笔记**：

每次提问时，`services/cet4_coach.py` 会把**最近 8 条笔记**（每条正文截断 220 字）拼进 system prompt，并明确要求：
引用笔记时原样引用、不得编造、可以用笔记里的错题和易混点出题。

实测效果（提问"我笔记里记了 affect 和 effect 的区别吗"）：

> 记了。你笔记里的要点（原样复述）：
> - affect 是动词（影响），effect 是名词（效果）。
> - 记法：A=Action 动作，E=End 结果。
> - 错题：The new policy may effect the agency. → 应为 affect。
> 一句话提醒：你错的那句里 agency 也是今天学的词，正好一起记。

> 说明：为了控制 token，只注入**最近 8 条**、且每条只取前 220 字；早期笔记不会自动带上。
> 想让更多笔记进上下文，改 `NotesService.recent_for_ai(limit=8, max_chars=220)` 的参数即可。

**数据位置**：`study_data/study.db` 的 `note` 表（和学习记录同一个库，切换词表不影响）。

---

## 九、数据与备份

- 每个单词列表 = `instance/` 下的一个 `.db` 文件（默认 `words.db`，自带 20 个示例词）。
- AI 助教聊天记录在 `chat_data/chat.db`。
- **每日学习记录 + 学习笔记**都在 `study_data/study.db`（`study_record` / `note` 两张表）。
- `study_data/cycle.db` 只是"本轮抽到哪了"的状态，**可以随便删**（删了下一轮重新开始）。
- **备份**：把 `instance/`、`chat_data/`、`study_data/` 三个目录一起复制（或网页上用「导出 CSV」导出词库）。
  数据库都是默认日志模式，没有 `-wal/-shm` 附加文件，直接拷 `.db` 也不会丢数据。
- 想单独备份笔记：`docker compose stop` 后复制 `study_data/study.db`；恢复时覆盖回去再 `docker compose start`。
- `docker compose down` 只删容器，不删这些目录；只有 `docker compose down -v` 或手动删目录才会丢数据。

---

## 十、常用命令速查

| 目的 | 命令 |
| --- | --- |
| 构建并启动 | `docker compose up -d --build` |
| 仅重启 | `docker compose restart` |
| 看实时日志 | `docker compose logs -f` |
| 看运行状态/端口 | `docker compose ps` |
| 进容器 | `docker compose exec wordnest bash` |
| 停止（保留数据） | `docker compose down` |
| 改了依赖后彻底重建 | `docker compose build --no-cache; docker compose up -d` |

---

## 十一、常见问题

**1. 打开 5000 端口没反应 / 502**
容器刚起来需要 1～3 秒初始化数据库，稍等一下；仍不行看 `docker compose logs`。

**2. 端口 5000 被占用**
改 `.env` 里的 `WORDNEST_PORT=5001`，再 `docker compose up -d`，访问 <http://localhost:5001>。

**3. 构建时 apt/pip 很慢或失败**
默认已用阿里云（apt）与清华（pip）镜像。若你挂了代理或在海外，可以覆盖：

```powershell
docker compose build --build-arg APT_MIRROR=https://deb.debian.org --build-arg PIP_INDEX_URL=https://pypi.org/simple
```

**4. `docker pull` 拉不动基础镜像**
你的 `~/.docker/daemon.json` 已配了三个镜像加速器；若失效，可在 Docker Desktop
→ Settings → Docker Engine 里换一个，或给 Docker Desktop 配代理（Settings → Resources → Proxies）。
本例中 `python:3.11-slim` 已经拉到本地，正常重建不需要再拉取。

**5. AI 功能报错 / 返回 500**
先确认 `.env` 里 Key 非空且已 `docker compose up -d` 重建；再确认容器能访问 `api.deepseek.com`：
`docker compose exec wordnest curl -sS -o /dev/null -w "%{http_code}\n" https://api.deepseek.com`
（返回 401 是正常的，说明连通、只是没带 Key。）

**5.1 AI 报 `SSL: UNEXPECTED_EOF_WHILE_READING` / `handshake operation timed out`**

这是**容器出网被宿主机代理拦住了**，典型触发场景：开了 Clash Verge 的 TUN 模式 / 系统代理。
诊断特征：宿主机能连 DeepSeek，但容器里 8 次全部超时或 EOF。

现在的处理：项目会先试 `WORDNEST_PROXY`（默认 `http://host.docker.internal:7897`），
失败自动回落直连。所以正常情况下你**不用开关代理**。

如果仍然失败：
- 确认代理端口写对（Clash Verge 7897 / Clash for Windows 7890），改 `.env` 后 `docker compose up -d`
- 或者干脆关掉代理再试（关代理后容器直连是通的）
- 验证：`docker compose exec wordnest python -c "from utils import net; print(net.request('GET','https://api.deepseek.com/',timeout=10).status_code)"`

**6. 朗读没声音**
容器内用 `espeak-ng` 合成 WAV 返回给浏览器，声音由你的浏览器播放，所以请确认浏览器没静音。
合成速度略慢（首次约 1 秒），属正常。

**7. 想更新到上游新版本**
`git pull`（如果本来就是 clone 的），或把新版本源码覆盖过来再 `docker compose up -d --build`。

**8. 能不能同时跑两个实例（比如一个测试一个自用）**
默认不行：`docker-compose.yml` 里 `container_name: wordnest` 是固定的，
而且 Compose 的"项目名"取目录名——两个都叫 `WordNest` 的目录会被当成同一个项目，
第二个实例会把第一个的容器**替换掉**（数据不会丢，但服务会切走）。

需要并存时，复制目录后改三处：`container_name`、宿主机端口（如 `"5001:5000"`），
并用 `docker compose -p 项目名 up -d` 指定不同项目名。

---

## 十二、VSCode 里怎么调试

- `F5` → `WordNest: Flask 调试 (端口 5000)`：以 `flask run --no-reload` 启动，断点有效。
- `F5` → `WordNest: 直接运行 app.py (debug)`：直接跑 `app.py`（会带 Flask 自动重载）。
- 调试端口固定 5000，和容器映射一致，浏览器直接刷 <http://localhost:5000> 即可。

> 注意：宿主机本地调试需要本机有 Python 3.8+ 并 `pip install -r requirements.txt`；
> 若只想跑起来，用 Docker 方式最省心。

---

## 十三、手机 / 远程访问（在手机上刷词）

**先说结论：不需要"同步"。** 词库、笔记、学习记录都在你电脑上这一个容器的 SQLite 里，
手机只是远程打开同一个网页，看到的自然是同一份数据——电脑上背到第 50 个词，手机打开就是第 50 个。

前提：**电脑开机 + Docker Desktop 在运行**（`docker compose up -d`），手机和电脑网络可达。

### 方式 A：同一个 Wi-Fi（最简单，先试这个）

1. 电脑上 `ipconfig` 查 WLAN 的 IPv4 地址（本机是 `10.48.23.69`）
2. 手机浏览器打开 `http://10.48.23.69:5000`
3. 打不开时按顺序排查：
   - **Windows 防火墙**（管理员 PowerShell 执行一次）：
     ```powershell
     New-NetFirewallRule -DisplayName "WordNest 5000" -Direction Inbound `
       -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private,Public
     ```
   - **校园网 / 公司网常开"客户端隔离"**：同一网段设备之间也互相 ping 不通，
     这种网络下 A 方案无解，改用 B。
   - 电脑进了睡眠：电源设置里关掉睡眠。

> 注意：局域网里同一 Wi-Fi 的其他人也能访问，建议设访问密码（见下）。

### 方式 B：Tailscale（推荐，宿舍/校外/流量都能用）

1. 电脑装 [Tailscale](https://tailscale.com/download)（Windows），登录账号
2. 手机装 Tailscale App，登录**同一个账号**
3. 在 Tailscale 面板里看电脑的 `100.x.y.z` 地址
4. 手机浏览器打开 `http://100.x.y.z:5000`

免费额度够个人用、不需要路由器端口映射、跨运营商可用，是最省心的长期方案。

### 方式 C：Cloudflare 临时公网链接（开箱可用，本机已配好）

本机已经把 `cloudflared.exe` 下好了（`..\tools\cloudflared.exe`，52.8MB），不用再装。

**一条命令启动**：

```powershell
.\start-tunnel.ps1
```

脚本会：检查本地 5000 是否在线 → 检查有没有设访问密码（没设会黄色警告并等 5 秒）→ 启动隧道 →
终端里出现 `https://xxx.trycloudflare.com`，手机用这个地址就能打开（流量也行）。

手动等价命令：

```powershell
..\tools\cloudflared.exe tunnel --url http://127.0.0.1:5000 --no-autoupdate
```

**实测数据**（2026-10-22 在本机验证）：

| 项 | 结果 |
| --- | --- |
| 建立隧道 | 约 3 秒，节点 `lax09/lax13`（洛杉矶） |
| 通过公网地址访问 `/` | **200**，返回「单词自测系统」，55.7KB |
| 访问 `/api/lists` | 200，返回正常 JSON |
| 访问 `/notes` | 200，返回「我的笔记 · WordNest」 |
| 单页往返耗时 | 约 **6.2~6.6 秒** |

**要注意的**：

- **延迟高**：流量绕道洛杉矶，每次页面跳转 6 秒左右，翻单词会有明显顿挫感；只适合临时用/给同学看，不适合天天刷词。
- **地址会变**：每次启动都是随机域名，关掉终端就失效。
- **没有可用性保证**：Cloudflare 明确说明 fast tunnel 不承诺稳定性，受其服务条款约束；正式长期用应建 named tunnel 绑自己的域名。
- **必须设密码**：公网可访问 = 任何人拿到地址都能进。先在 `.env` 里设 `WORDNEST_PASSWORD=...`，再 `docker compose up -d`。
  设了密码后，陌生人只会看到登录页，看不到你的词库。

**什么时候选它**：临时演示、给同学看一眼、自己在外面应急查个词。
**想要每天稳定刷词**：选方式 B（Tailscale），延迟低得多、地址固定、还不用暴露公网。

### 方式 D：国内内网穿透（花生壳 / 樱花 frp 等）

需要注册账号、装客户端、配映射，适合想要固定域名的人；配置比 B/C 麻烦。

### 访问密码（外网访问必看）

WordNest 默认没有登录，任何能打开这个网址的人都能删你的单词/笔记、还能消耗你的 DeepSeek 额度。

开启方式（`.env` 里加一行，然后 `docker compose up -d`）：

```ini
WORDNEST_PASSWORD=你的密码
```

- 设置后所有页面先跳 `/login`，输入密码才能进（登录态存 Cookie，有效期随浏览器会话）
- 未登录访问接口返回 `401`（AI 侧栏也能正确提示）
- 忘记密码：改 `.env` 重启即可，不影响数据；想彻底关掉就把这行留空
- 密码用环境变量传入，不写进代码库

### 手机端体验

- 窄屏下左侧 AI 助教会**自动收起成左下角一个小圆钮**，点开是底部浮层，不再挡住单词卡
- 单词和操作图标改成上下排列，长单词（`intelligent`、`discrimination`）不会压到按钮
- 建议手机浏览器「添加到主屏幕」，用起来接近 App
