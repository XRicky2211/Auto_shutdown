# --------------------------------------------------------------------------
# 文件：core/config_manager.py
# 用途：用户配置的 JSON 持久化（保存/读取）
# --------------------------------------------------------------------------

import json
import os
import sys


def _config_path() -> str:
    """获取配置文件路径：打包后使用 %APPDATA%，开发环境使用项目目录"""
    if getattr(sys, "frozen", False):
        app_dir = os.path.join(os.environ["APPDATA"], "AutoShutdownHelper")
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, "settings.json")
    return os.path.join(os.path.dirname(__file__), "..", "settings.json")


def load_settings() -> dict:
    """从 JSON 读取配置，文件不存在时返回空字典"""
    path = _config_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(**kwargs):
    """保存配置到 JSON 文件（按 key 分组，合并已有配置）"""
    path = _config_path()

    existing = load_settings()
    existing.update(kwargs)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
