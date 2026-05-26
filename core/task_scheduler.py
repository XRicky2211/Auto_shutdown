# --------------------------------------------------------------------------
# 文件：core/task_scheduler.py
# 用途：使用 Windows 任务计划程序 (schtasks) 管理定时关机任务
#        支持从睡眠中唤醒执行 (/WAKE)，且不会产生系统通知弹窗
# --------------------------------------------------------------------------

import subprocess
import sys

from PySide6.QtCore import QDateTime

TASK_NAME = "AutoShutdownHelper"

# 任务类型对应的实际命令行
TASK_COMMANDS = {
    "shutdown":  "shutdown /s /t 0",
    "restart":   "shutdown /r /t 0",
    "logout":    "shutdown /l",
    "sleep":     "rundll32.exe powrprof.dll,SetSuspendState 0,0,0",
    "hibernate": "shutdown /h",
}


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


def schedule_task(target_time: QDateTime, task_type: str = "shutdown") -> bool:
    """在指定时间安排关机/重启等任务。

    首先尝试带 /WAKE 参数（可从睡眠中唤醒），若权限不足则回退到普通任务。
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
