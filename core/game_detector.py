# --------------------------------------------------------------------------
# 文件：core/game_detector.py
# 用途：通过 Windows API 检测前台窗口是否为全屏程序
# --------------------------------------------------------------------------

import ctypes
from ctypes import wintypes

SM_CXSCREEN = 0
SM_CYSCREEN = 1

EXCLUDED_CLASSES = frozenset({
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
})


class RECT(ctypes.Structure):
    _fields_ = [
        ("left",   wintypes.LONG),
        ("top",    wintypes.LONG),
        ("right",  wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


def is_fullscreen_app_running() -> bool:
    """检测当前前台窗口是否为全屏游戏/应用程序。

    判断逻辑：
        1. 获取前台窗口句柄
        2. 获取窗口类名，排除桌面、任务栏等系统窗口
        3. 获取窗口尺寸，与屏幕分辨率对比（>=95% 面积视为全屏）

    返回 True 表示正在运行全屏程序。
    """
    user32 = ctypes.windll.user32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False

    class_name = _get_window_class(user32, hwnd)
    if class_name in EXCLUDED_CLASSES:
        return False

    screen_w = user32.GetSystemMetrics(SM_CXSCREEN)
    screen_h = user32.GetSystemMetrics(SM_CYSCREEN)
    screen_area = screen_w * screen_h
    if screen_area <= 0:
        return False

    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False

    win_w = rect.right - rect.left
    win_h = rect.bottom - rect.top
    win_area = win_w * win_h

    return (win_area / screen_area) >= 0.95


def _get_window_class(user32, hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value
