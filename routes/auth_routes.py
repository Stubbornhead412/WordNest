"""登录 / 登出路由（只有设置了 WORDNEST_PASSWORD 时才会真正用到）"""
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from utils.auth import auth_enabled, verify_password

auth_bp = Blueprint('auth', __name__)


def _safe_next(target):
    """只允许站内相对跳转，防开放重定向"""
    target = (target or '').strip()
    if not target.startswith('/') or target.startswith('//'):
        return '/'
    return target


@auth_bp.route('/login', methods=['GET', 'POST'])
def login_page():
    if not auth_enabled():
        # 没设密码就直接进站
        return redirect('/')

    error = None
    next_url = _safe_next(request.args.get('next') or request.form.get('next') or '/')

    if request.method == 'POST':
        if verify_password(request.form.get('password', '')):
            session['access_ok'] = True
            session.permanent = True
            return redirect(next_url)
        error = '密码不对，再试一次'

    return render_template('login.html', error=error, next_url=next_url, enabled=True)


@auth_bp.route('/logout')
def logout():
    session.pop('access_ok', None)
    return redirect(url_for('auth.login_page'))
