# --------------------------------------------------------------------------
# 文件：core/brightness_controller.py
# 用途：Windows 笔记本屏幕亮度读写（通过 PowerShell WMI，零额外依赖）
# --------------------------------------------------------------------------

import subprocess
import sys
from typing import Optional


def get_brightness() -> Optional[int]:
    """获取当前屏幕亮度（0-100）。

    通过 WMI WmiMonitorBrightness 类读取笔记本内置屏幕的当前亮度值。
    如果设备没有内置屏幕（台式机 + 外接显示器）或调用失败，返回 None。
    """
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness)"
                ".CurrentBrightness",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
            if sys.platform == "win32" else 0,
        )
        stdout = result.stdout.strip()
        if result.returncode == 0 and stdout:
            return int(stdout)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return None


def set_brightness(level: int) -> bool:
    """设置屏幕亮度（0-100）。

    通过 WMI WmiMonitorBrightnessMethods 类设置笔记本内置屏幕亮度。
    第一个参数为超时秒数（0 表示立即执行），第二个为亮度值。

    返回 True 表示命令执行成功，False 表示失败。
    """
    level = max(0, min(100, int(level)))
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
                f".WmiSetBrightness(0, {level})",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
            if sys.platform == "win32" else 0,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False
