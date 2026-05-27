# --------------------------------------------------------------------------
# 文件：core/power_manager.py
# 用途：封装 Windows 电源管理 API，阻止系统在关键时段进入睡眠
#
# 双 API 覆盖：
#   SetThreadExecutionState  → 传统 S3 睡眠
#   PowerCreateRequest       → Modern Standby (S0 低功耗空闲)
# --------------------------------------------------------------------------

import atexit
import ctypes
from ctypes import wintypes


# ---- 常量 ----

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

# POWER_REQUEST_CONTEXT 标志
POWER_REQUEST_CONTEXT_VERSION = 1
POWER_REQUEST_CONTEXT_SIMPLE_STRING = 0x00000001

# PowerRequestType
PowerRequestSystemRequired = 1


# ---- POWER_REQUEST_CONTEXT 结构体 ----

class POWER_REQUEST_CONTEXT(ctypes.Structure):
    _fields_ = [
        ("Version",       wintypes.ULONG),
        ("Flags",         wintypes.ULONG),
        ("SimpleReasonString", wintypes.LPCWSTR),
    ]


# ---- 内部单例 ----

class _PowerManager:
    def __init__(self):
        self._power_request_handle = None
        self._request_context = None
        self._sleep_blocked = False

    def prevent_sleep(self, reason: str = "") -> bool:
        if self._sleep_blocked:
            return True

        ok_legacy = False
        ok_modern = False

        # 方法 1：SetThreadExecutionState（传统 S3 睡眠）
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.SetThreadExecutionState(
                wintypes.DWORD(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            )
            ok_legacy = True
        except Exception:
            pass

        # 方法 2：PowerCreateRequest（Modern Standby S0）
        try:
            kernel32 = ctypes.windll.kernel32
            request_context = POWER_REQUEST_CONTEXT()
            request_context.Version = POWER_REQUEST_CONTEXT_VERSION
            request_context.Flags = POWER_REQUEST_CONTEXT_SIMPLE_STRING
            request_context.SimpleReasonString = reason or "Auto shutdown countdown active"

            handle = wintypes.HANDLE()
            result = kernel32.PowerCreateRequest(
                ctypes.byref(request_context),
                ctypes.byref(handle),
            )
            if result != 0:  # 非零 = 成功
                kernel32.PowerSetRequest(
                    handle,
                    wintypes.DWORD(PowerRequestSystemRequired),
                )
                self._power_request_handle = handle
                self._request_context = request_context
                ok_modern = True
        except Exception:
            pass

        self._sleep_blocked = ok_legacy or ok_modern
        return self._sleep_blocked

    def allow_sleep(self) -> bool:
        if not self._sleep_blocked:
            return True

        # 恢复 SetThreadExecutionState
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.SetThreadExecutionState(wintypes.DWORD(ES_CONTINUOUS))
        except Exception:
            pass

        # 释放 PowerCreateRequest
        if self._power_request_handle is not None:
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.PowerClearRequest(
                    self._power_request_handle,
                    wintypes.DWORD(PowerRequestSystemRequired),
                )
                kernel32.CloseHandle(self._power_request_handle)
            except Exception:
                pass
            self._power_request_handle = None
            self._request_context = None

        self._sleep_blocked = False
        return True

    def is_sleep_blocked(self) -> bool:
        return self._sleep_blocked


_power_manager = _PowerManager()


# ---- 模块级接口 ----

def prevent_sleep(reason: str = "") -> bool:
    """阻止系统进入睡眠（幂等调用，可多次安全调用）"""
    return _power_manager.prevent_sleep(reason)


def allow_sleep() -> bool:
    """恢复系统正常睡眠行为"""
    return _power_manager.allow_sleep()


def is_sleep_blocked() -> bool:
    """查询当前是否正在阻止系统睡眠"""
    return _power_manager.is_sleep_blocked()


# ---- 退出时自动清理 ----

def _cleanup():
    if _power_manager is not None:
        _power_manager.allow_sleep()

atexit.register(_cleanup)
