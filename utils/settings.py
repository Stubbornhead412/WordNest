"""
设置管理工具

settings.json 是纯界面偏好（是否只抽查星标、显示模式等），不包含任何个人数据。
这里做了容错：
- 文件不存在：使用默认值并尝试创建
- 路径是目录（Docker 挂载宿主机上不存在的文件时会创建成目录）：退回默认值，不抛异常
- 内容损坏 / 无读权限：退回默认值，不抛异常
"""
import json
import os

SETTINGS_FILE = 'settings.json'

DEFAULT_SETTINGS = {
    'marked_only': False,
    'display_mode': 'word_only',
    'sort_mode': 'alphabetical',
    'filter_mode': 'all',
}


def load_settings():
    """加载系统设置；出现任何异常都返回默认值，保证页面可用"""
    try:
        if os.path.isdir(SETTINGS_FILE):
            # Docker 把不存在的挂载点创建成了目录：无法读写，直接用默认值
            return dict(DEFAULT_SETTINGS)
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                merged = dict(DEFAULT_SETTINGS)
                merged.update(data)
                return merged
            return dict(DEFAULT_SETTINGS)
    except (OSError, ValueError):
        return dict(DEFAULT_SETTINGS)

    # 首次运行：写入默认配置文件（失败也不影响使用）
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except OSError:
        pass
    return settings


def save_settings(settings):
    """保存系统设置；路径不可写时静默失败（不影响当前请求）"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return True
    except (OSError, TypeError):
        return False
