# WordNest - Flask 个性化英语单词学习系统
# 注意：这里刻意不写 "# syntax=docker/dockerfile:1"，
# 因为该前端镜像需要联网拉取，国内网络下容易卡住；用 BuildKit 内置前端即可。
# 说明：python:3.11-slim 与项目锁定的 Flask 2.2.5 / Werkzeug 2.2.3 兼容性最好。
FROM python:3.11-slim

# 默认走国内镜像源（deb.debian.org 在国内基本连不上）。
# 如在海外 / 有代理，可覆盖为：
#   docker compose build --build-arg APT_MIRROR=https://deb.debian.org --build-arg PIP_INDEX_URL=https://pypi.org/simple
ARG APT_MIRROR=https://mirrors.aliyun.com
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    TZ=Asia/Shanghai

# espeak-ng：pyttsx3 朗读单词所需语音引擎（Linux 下缺少它 pyttsx3.init() 会报错）
# curl：容器健康检查用
RUN for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
        [ -f "$f" ] && sed -i -E "s#https?://deb\.debian\.org#${APT_MIRROR}#g" "$f"; \
    done \
    && apt-get update -o Acquire::Retries=3 \
    && apt-get install -y --no-install-recommends espeak-ng libespeak-ng1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖，利用 Docker 层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -i "${PIP_INDEX_URL}" \
        -r requirements.txt gunicorn==23.0.0

# 再拷业务代码
COPY . .

# 数据目录（词库数据库、AI 聊天记录）
RUN mkdir -p /app/instance /app/chat_data

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:5000/ >/dev/null || exit 1

# 单 worker + 多线程：项目会在每个请求里动态切换 SQLite 引擎，
# 多进程 worker 各自持有独立引擎容易数据不一致，1 个 worker 足够个人背单词使用。
CMD ["gunicorn", "--workers", "1", "--threads", "8", \
     "--bind", "0.0.0.0:5000", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "app:app"]
