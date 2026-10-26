"""
统一的外部 HTTP 出口（主要给 DeepSeek 等外网 API 用）

为什么需要它：容器里的出网要和宿主机代理共存。用户开了 Clash 之类的代理
（尤其是 TUN / 系统代理模式）后，WSL 容器的直连 TLS 会被掐断
（SSL: UNEXPECTED_EOF_WHILE_READING / 握手超时），但容器可以访问宿主机的代理端口。

策略：
1. 配置了 WORDNEST_PROXY（默认 http://host.docker.internal:7897）就先走代理；
   代理没开时连接会立刻被拒，代价极小
2. 代理失败或未配置则直连
3. 网络类错误最多重试 2 轮；HTTP 状态码错误不重试（那是业务问题，重试也没用）
"""
import os

import requests
from flask import current_app, has_app_context

# 代理尝试用短连接超时，直连给长一点（TLS 握手挂住时会等到超时）
CONNECT_TIMEOUT_PROXY = 3
CONNECT_TIMEOUT_DIRECT = 6


def proxy_url():
    """读取代理地址：优先 app config，其次环境变量"""
    url = ''
    if has_app_context():
        url = (current_app.config.get('OUTBOUND_PROXY')
               or current_app.config.get('WORDNEST_PROXY')
               or '')
    if not url:
        url = os.environ.get('WORDNEST_PROXY', '')
    return (url or '').strip()


def request(method, url, *, timeout=30, rounds=2, **kwargs):
    """
    先代理、后直连地发一次请求，网络错误自动换路/重试。

    Args:
        method: HTTP 方法
        url: 目标地址
        timeout: 读超时（秒）
        rounds: 整体轮数（每轮包含"代理 + 直连"两次尝试）
        **kwargs: 透传给 requests（headers / json / stream 等）

    Returns:
        requests.Response

    Raises:
        最后一次尝试的 requests 异常
    """
    proxy = proxy_url()
    plan = []
    if proxy:
        plan.append(('proxy', {'http': proxy, 'https': proxy}, CONNECT_TIMEOUT_PROXY))
    plan.append(('direct', None, CONNECT_TIMEOUT_DIRECT))

    last_error = None
    for _ in range(max(1, rounds)):
        for name, proxies, connect_timeout in plan:
            try:
                resp = requests.request(
                    method, url,
                    timeout=(connect_timeout, timeout),
                    proxies=proxies,
                    **kwargs
                )
                if name == 'proxy' and resp.status_code >= 500:
                    # 代理自己报错时再试直连
                    last_error = requests.exceptions.HTTPError(
                        f'代理返回 {resp.status_code}', response=resp)
                    continue
                return resp
            except requests.exceptions.RequestException as e:
                last_error = e
                continue
    raise last_error or requests.exceptions.ConnectionError('请求失败')


def describe_error(exc):
    """把网络异常翻译成给用户看的中文提示"""
    if isinstance(exc, requests.exceptions.SSLError):
        return ('连不上 DeepSeek：TLS 握手被打断。通常是代理/校园网拦截了容器的出网，'
                '请确认 Clash 等代理已开启，或稍后重试。')
    if isinstance(exc, requests.exceptions.Timeout):
        return '请求超时：网络较慢或代理不稳定，请重试。'
    if isinstance(exc, requests.exceptions.ProxyError):
        return '代理连接失败：请检查 .env 里的 WORDNEST_PROXY 是否指向正在运行的代理端口。'
    if isinstance(exc, requests.exceptions.ConnectionError):
        return '网络连接失败：请检查网络，或确认代理是否正常。'
    return f'请求出错：{exc}'
