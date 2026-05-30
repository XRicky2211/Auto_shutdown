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

# InitiateShutdown 所需的常量
SHUTDOWN_FORCE_OTHERS = 0x00000001
SHUTDOWN_POWEROFF = 0x00000008
SHUTDOWN_RESTART = 0x00000004
SHUTDOWN_HYBRID = 0x00000200

SHTDN_REASON_MAJOR_APPLICATION = 0x00040000
SHTDN_REASON_FLAG_PLANNED = 0x80000000


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


# ======================== 直接执行关机/重启（Win32 API） ========================

def _enable_shutdown_privilege() -> bool:
    """启用当前进程的 SE_SHUTDOWN_NAME 特权。"""
    try:
        advapi32 = ctypes.windll.advapi32
        kernel32 = ctypes.windll.kernel32

        h_token = wintypes.HANDLE()
        TOKEN_ADJUST_PRIVILEGES = 0x0020
        TOKEN_QUERY = 0x0008
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(),
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            ctypes.byref(h_token),
        ):
            return False

        luid = wintypes.LUID()
        if not advapi32.LookupPrivilegeValueW(None, "SeShutdownPrivilege", ctypes.byref(luid)):
            return False

        SE_PRIVILEGE_ENABLED = 0x00000002

        class LUID_AND_ATTRIBUTES(ctypes.Structure):
            _fields_ = [
                ("Luid", wintypes.LUID),
                ("Attributes", wintypes.DWORD),
            ]

        class TOKEN_PRIVILEGES(ctypes.Structure):
            _fields_ = [
                ("PrivilegeCount", wintypes.DWORD),
                ("Privileges", LUID_AND_ATTRIBUTES * 1),
            ]

        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0] = LUID_AND_ATTRIBUTES()
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

        if not advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None):
            return False

        kernel32.CloseHandle(h_token)
        return True
    except Exception:
        return False


def force_shutdown():
    """通过 Win32 InitiateShutdown API 直接关机，不依赖 shutdown.exe。

    在 Modern Standby (S0) 系统上，subprocess.Popen(shutdown.exe) 可能
    因系统重新进入低功耗空闲状态而失败。此 API 直接向 Windows 发送关机
    请求，可靠性更高。
    """
    try:
        advapi32 = ctypes.windll.advapi32
        _enable_shutdown_privilege()

        func = advapi32.InitiateShutdownW
        func.argtypes = [
            wintypes.LPCWSTR,  # lpMachineName
            wintypes.LPCWSTR,  # lpMessage
            wintypes.DWORD,    # dwGracePeriod
            wintypes.DWORD,    # dwShutdownFlags
            wintypes.DWORD,    # dwReason
        ]
        func.restype = wintypes.BOOL

        flags = SHUTDOWN_FORCE_OTHERS | SHUTDOWN_POWEROFF
        reason = SHTDN_REASON_MAJOR_APPLICATION | SHTDN_REASON_FLAG_PLANNED

        result = func(None, None, 0, flags, reason)
        return bool(result)
    except Exception:
        return False


def force_restart():
    """通过 Win32 InitiateShutdown API 直接重启系统。"""
    try:
        advapi32 = ctypes.windll.advapi32
        _enable_shutdown_privilege()

        func = advapi32.InitiateShutdownW
        func.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        func.restype = wintypes.BOOL

        flags = SHUTDOWN_FORCE_OTHERS | SHUTDOWN_RESTART
        reason = SHTDN_REASON_MAJOR_APPLICATION | SHTDN_REASON_FLAG_PLANNED

        result = func(None, None, 0, flags, reason)
        return bool(result)
    except Exception:
        return False


# ---- 退出时自动清理 ----

def _cleanup():
    if _power_manager is not None:
        _power_manager.allow_sleep()

atexit.register(_cleanup)
