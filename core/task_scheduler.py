# --------------------------------------------------------------------------
# 文件：core/task_scheduler.py
# 用途：使用 Windows 任务计划程序 (schtasks) 管理定时关机任务
#        支持从睡眠中唤醒执行 (/WAKE)，且不会产生系统通知弹窗
#        支持低电量巡检任务（系统睡眠时通过计划任务检测电池）
# --------------------------------------------------------------------------

import os
import subprocess
import sys
import tempfile

from PySide6.QtCore import QDateTime

TASK_NAME = "AutoShutdownHelper"
BATTERY_TASK_NAME = "AutoShutdownBatteryCheck"

# 任务类型对应的实际命令行
TASK_COMMANDS = {
    "shutdown":  "shutdown /s /t 0",
    "restart":   "shutdown /r /t 0",
    "logout":    "shutdown /l",
    "sleep":     "rundll32.exe powrprof.dll,SetSuspendState 0,0,0",
    "hibernate": "shutdown /h",
}

# ---- 电源 GUID（用于 powercfg） ----
SUB_SLEEP_GUID = "238C9FA8-0AAD-41ED-83F4-97BE242C8F20"
RTCWAKE_GUID = "BD3B718A-0680-4D9D-8AB2-E1D2B4AC806D"


def _run_schtasks(args: list) -> bool:
    """执行 schtasks 命令，静默运行"""
    try:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW  # type: ignore
        result = subprocess.run(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def _run_powercfg(args: list) -> bool:
    """静默执行 powercfg 命令"""
    try:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            ["powercfg"] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def detect_modern_standby() -> bool:
    """检测系统是否使用 Modern Standby (S0 低功耗空闲)。

    通过 powercfg /a 输出判断。S0 模式下传统的 RTC 唤醒定时器不可靠，
    /WAKE 参数可能无法从 S0 睡眠中唤醒系统。
    """
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run(
            ["powercfg", "/a"],
            capture_output=True, text=True, timeout=5,
            creationflags=flags,
        )
        output = result.stdout + result.stderr
        return ("待机(S0 低功耗空闲)" in output or
                "Standby (S0 Low Power Idle)" in output or
                "待机 (S0 低电量待机)" in output)
    except Exception:
        return False


def _enable_wake_timers() -> bool:
    """启用系统唤醒定时器，使计划任务的 /WAKE 参数真正生效。

    通过 powercfg 修改当前电源方案，允许唤醒定时器唤醒系统。
    相当于：控制面板 → 电源选项 → 更改计划设置 → 更改高级电源设置
          → 睡眠 → 允许唤醒定时器 → 启用
    """
    ok = True
    # 直流（电池）模式
    if not _run_powercfg(["/setdcvalueindex", "SCHEME_CURRENT",
                          SUB_SLEEP_GUID, RTCWAKE_GUID, "1"]):
        ok = False
    # 交流（电源）模式
    if not _run_powercfg(["/setacvalueindex", "SCHEME_CURRENT",
                          SUB_SLEEP_GUID, RTCWAKE_GUID, "1"]):
        ok = False
    # 生效
    _run_powercfg(["/setactive", "SCHEME_CURRENT"])
    return ok


def schedule_task(target_time: QDateTime, task_type: str = "shutdown") -> bool:
    """在指定时间安排关机/重启等任务。

    首先尝试启用以唤醒定时器，再创建带 /WAKE 参数的任务（可从睡眠中唤醒），
    若权限不足则回退到普通任务。

    target_time: 目标执行时间 (QDateTime)
    task_type: shutdown / restart / logout / sleep / hibernate
    返回 True 表示创建成功。
    """
    cmd_str = TASK_COMMANDS.get(task_type, "shutdown /s /t 0")
    time_str = target_time.toString("HH:mm")
    date_str = target_time.toString("yyyy/MM/dd")

    base = [
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", cmd_str,
        "/sc", "once",
        "/st", time_str,
        "/sd", date_str,
        "/f",
    ]

    # 启用唤醒定时器，让 /WAKE 能真正唤醒系统
    _enable_wake_timers()

    # 第一次尝试带 /WAKE（需要管理员权限）
    if _run_schtasks(base + ["/WAKE"]):
        return True

    # 回退：不带 /WAKE
    return _run_schtasks(base)


def cancel_task() -> bool:
    """取消已安排的定时任务。若任务不存在则静默返回 True。"""
    return _run_schtasks([
        "schtasks", "/delete", "/tn", TASK_NAME, "/f",
    ])


# ======================== 低电量巡检（独立于 Python 进程） ========================
#
# 当系统进入睡眠后，Python 进程被挂起，无法检测电池电量。
# 以下函数创建一个 Windows 计划任务，每 5 分钟执行一次电池检测脚本，
# 即使系统睡眠也能通过 /WAKE 唤醒执行，确保低电量关机可靠触发。


def _get_battery_script_path() -> str:
    """获取临时电池检测脚本路径"""
    return os.path.join(tempfile.gettempdir(), "AutoShutdownBatteryCheck.bat")


def _write_battery_script(threshold: int) -> str:
    """创建电池检测批处理脚本，返回脚本路径；失败返回空字符串"""
    script = (
        f'@powershell -NoProfile -ExecutionPolicy Bypass -Command '
        f'"if((Get-WmiObject Win32_Battery).EstimatedChargeRemaining -le {threshold} '
        f'-and (Get-WmiObject Win32_Battery).BatteryStatus -ne 2){{shutdown /s /t 0}}"'
    )
    path = _get_battery_script_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(script)
        return path
    except Exception:
        return ""


def schedule_low_battery_task(threshold: int) -> bool:
    """创建定时检测低电量的巡检任务（每5分钟），系统睡眠时也能唤醒执行。

    此任务完全独立于 Python 进程，由 Windows 任务计划程序调度。
    threshold: 低电量阈值（百分比）
    """
    script_path = _write_battery_script(threshold)
    if not script_path:
        return False

    # 将脚本路径包装在 cmd.exe 中执行，避免路径空格问题
    cmd = f'cmd.exe /c "{script_path}"'

    base = [
        "schtasks", "/create",
        "/tn", BATTERY_TASK_NAME,
        "/tr", cmd,
        "/sc", "minute",
        "/mo", "5",
        "/f",
    ]

    # 启用唤醒定时器
    _enable_wake_timers()

    if _run_schtasks(base + ["/WAKE"]):
        return True
    return _run_schtasks(base)


def cancel_low_battery_task() -> bool:
    """取消低电量巡检任务并清理临时脚本"""
    result = _run_schtasks([
        "schtasks", "/delete", "/tn", BATTERY_TASK_NAME, "/f",
    ])
    # 清理临时脚本
    try:
        os.remove(_get_battery_script_path())
    except (FileNotFoundError, PermissionError):
        pass
    return result
