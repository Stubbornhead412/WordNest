"""
简单访问密码

场景：把 WordNest 暴露到局域网 / 内网穿透 / 公网隧道后，防止别人直接打开你的词库
（否则任何人都能删你的单词、消耗你的 DeepSeek 额度）。

开关：环境变量 WORDNEST_PASSWORD
- 留空（默认）：不启用，和以前完全一样
- 设置后：除 /login 和静态资源外，所有页面与接口都要求先登录

因为只在个人电脑上跑，用 Flask session（签名 Cookie）记录登录态即可，
不引入用户表/密码哈希等复杂度；密码本身从环境变量读取，不落代码库。
"""
import hmac

from flask import current_app, jsonify, redirect, request, session, url_for

# 免登录路径（前缀匹配）
PUBLIC_PREFIXES = ('/static/', '/login', '/favicon.ico')


def auth_enabled():
    return bool(current_app.config.get('ACCESS_PASSWORD'))


def is_authenticated():
    return bool(session.get('access_ok'))


def check_access():
    """
    在 before_request 里调用。

    Returns:
        None 表示放行；否则返回一个 Flask Response（重定向到登录页 / 401 JSON）
    """
    if not auth_enabled() or is_authenticated():
        return None

    path = request.path or '/'
    if path.startswith(PUBLIC_PREFIXES):
        return None

    # 接口类请求返回 401，避免前端拿到登录页 HTML
    wants_json = (
        path.startswith('/api/')
        or path.startswith('/ai/')
        or path.startswith('/notes/api')
        or path.startswith('/get_')
        or path.startswith('/mark_word')
        or path.startswith('/unmark_word')
        or path.startswith('/toggle_')
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.headers.get('Accept') or '')
    )
    if wants_json:
        return jsonify({'error': '未登录，请先在 /login 输入访问密码'}), 401

    return redirect(url_for('auth.login_page', next=request.full_path if request.query_string else path))


def verify_password(candidate):
    """常量时间比较，避免时序侧信道"""
    expected = current_app.config.get('ACCESS_PASSWORD') or ''
    if not expected:
        return True
    return hmac.compare_digest(str(candidate or ''), expected)
