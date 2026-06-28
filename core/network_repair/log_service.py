# --------------------------------------------------------------------------
# 文件：core/network_repair/log_service.py
# 用途：网络诊断与修复模块的日志服务——统一日志写入/读取/导出
# 说明：纯逻辑模块，不依赖 Qt；日志按日期分文件存储
# --------------------------------------------------------------------------

import os
import sys
import threading
from datetime import datetime
from typing import List

from .models import LogEntry

_LOG_DIR = "network_repair_logs"
_LOG_FILE = None  # 首次使用时会初始化
_LOCK = threading.Lock()  # 日志写入线程锁


def _get_log_dir() -> str:
    """获取日志目录路径（打包后 %APPDATA%，开发时项目根目录）"""
    if getattr(sys, "frozen", False):
        base = os.path.join(os.environ["APPDATA"], "AutoShutdownHelper")
    else:
        base = os.path.join(os.path.dirname(__file__), "..", "..")
    return os.path.join(base, _LOG_DIR)


def _ensure_log_file() -> str:
    """确保日志文件存在并返回路径"""
    global _LOG_FILE
    if _LOG_FILE is None:
        log_dir = _get_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        _LOG_FILE = os.path.join(
            log_dir,
            f"network_repair_{datetime.now().strftime('%Y%m%d')}.log",
        )
    return _LOG_FILE


def write_log(action: str, result: str = "", detail: str = "") -> None:
    """写入一条日志

    参数：
        action: 操作类型（如 "诊断" / "一键修复" / "高级修复" / "异常" / "导出"）
        result: 结果（如 "成功" / "失败" / "完成"）
        detail: 详细信息 / 错误描述
    """
    filepath = _ensure_log_file()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _LOCK:
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{action}] {result}")
                if detail:
                    f.write(f" | {detail}")
                f.write("\n")
        except OSError:
            pass


def write_log_entry(entry: LogEntry) -> None:
    """写入 LogEntry 对象"""
    write_log(entry.action, entry.result, entry.detail)


def read_log_lines() -> List[str]:
    """读取所有日志行"""
    filepath = _ensure_log_file()
    if not os.path.isfile(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.readlines()
    except OSError:
        return []


def get_log_path() -> str:
    """获取当前日志文件路径（用于导出）"""
    return _ensure_log_file()


def export_logs(export_path: str) -> bool:
    """导出日志到指定路径"""
    try:
        lines = read_log_lines()
        dir_name = os.path.dirname(export_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        write_log("导出", "成功", f"日志导出至 {export_path}")
        return True
    except OSError as e:
        write_log("导出", "失败", str(e))
        return False
