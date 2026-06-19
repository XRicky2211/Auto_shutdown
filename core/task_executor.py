# --------------------------------------------------------------------------
# 文件：core/task_executor.py
# 用途：统一执行入口——关机/重启/注销/睡眠/休眠
# 原则：纯逻辑模块，不依赖 Qt，不产生 Windows 倒计时提示
# --------------------------------------------------------------------------

import ctypes
import subprocess
import time
from datetime import datetime

from core.notification.email_sender import EmailSender


# ---- 5 种任务类型的命令映射 ----
# 关机 / 重启加 /f 强制关闭应用，避免 Windows 弹出"阻止关机"提示
# 不加 /t 参数（默认 0，等效 /t 0），不产生系统级倒计时横幅
_TASK_COMMANDS = {
    "shutdown": ["shutdown", "/s", "/f", "/t", "0"],
    "restart":  ["shutdown", "/r", "/f", "/t", "0"],
    "logout":   ["shutdown", "/l"],
    "hibernate":["shutdown", "/h"],
    # 睡眠不在此处定义，通过 Win32 API 执行
}


class TaskExecutor:
    """统一的任务执行器

    职责：
    - 提供 execute() 唯一入口执行 5 种任务
    - 防止同一任务被重复执行（is_shutting_down 标志）
    - 睡眠使用 Win32 SetSuspendState，不经过 rundll32
    - 所有任务静默执行，不触发 Windows 系统提示
    - 执行关机/重启/注销后发送邮件通知（可选）
    """

    def __init__(self):
        self.is_shutting_down = False
        self.email_enabled = False
        self.email_config = None

    # ======================== 公共接口 ========================

    def set_email_config(self, enabled: bool, config: dict):
        """设置邮件通知配置

        参数：
            enabled: 是否启用邮件通知
            config: 邮件配置字典
        """
        self.email_enabled = enabled
        self.email_config = config

    def execute(self, task_type: str, cause: str = ""):
        """执行指定类型的系统任务

        参数：
            task_type: "shutdown" / "restart" / "logout" /
                       "sleep"    / "hibernate"
            cause:     触发原因（countdown / schedule_once / schedule_daily /
                       schedule_weekdays / schedule_weekends / schedule_weekly /
                       low_battery），仅用于邮件正文区分
        返回：
            (success: bool, error_msg: str)
        """
        if self.is_shutting_down:
            return False, "已有任务正在执行"

        self.is_shutting_down = True

        # 生成唯一 task_id，用于邮件幂等发送
        task_id = f"{task_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # ---- 所有任务：先确保邮件发送成功 ----
        # 一直重试直到邮件成功（没有超时），用户收到确认后再执行
        if not self._send_email_until_success(task_type, task_id, cause):
            self.is_shutting_down = False
            return False, "邮件发送失败，无法执行系统任务"

        # ---- 邮件已确认成功，等待 5 秒再执行系统任务 ----
        time.sleep(5)

        try:
            if task_type == "sleep":
                self._execute_sleep()
            else:
                self._execute_command(task_type)

            return True, ""
        except Exception as e:
            self.is_shutting_down = False
            return False, str(e)

    def reset(self):
        """重置执行状态（供外部在任务失败或取消时调用）"""
        self.is_shutting_down = False

    def force_shutdown(self, cause: str = ""):
        """始终执行关机（用于低电量等紧急场景）"""
        return self.execute("shutdown", cause)

    # ======================== 内部实现 ========================

    def _send_email_until_success(self, task_type: str, task_id: str,
                                   cause: str = "") -> bool:
        """持续重试发送邮件，直到成功（无超时）"""
        if not self.email_enabled or not self.email_config:
            return True  # 未启用视为成功

        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sender = EmailSender(
            self.email_config.get("smtp_server", "smtp.163.com"),
            self.email_config.get("port", 465),
            self.email_config.get("user", ""),
            self.email_config.get("password", ""),
            self.email_config.get("to_email", ""),
        )

        while True:
            if sender.send_with_retry(
                task_type, time_str, task_id, cause,
                max_retries=3,
                retry_delay=3.0,
            ):
                return True

            # 重试一轮失败后，等几秒再试
            time.sleep(5)

    @staticmethod
    def _execute_command(task_type: str):
        """通过 subprocess 执行系统命令

        使用 subprocess.Popen（非阻塞），与原有代码行为一致。
        不等待进程结束，避免阻塞调用方。
        """
        cmd = _TASK_COMMANDS.get(task_type)
        if cmd is None:
            raise ValueError(f"不支持的任务类型: {task_type}")
        subprocess.Popen(cmd)

    @staticmethod
    def _execute_sleep():
        """通过 Win32 API 使系统进入睡眠状态

        使用 SetSuspendState(False, False, False)：
        - 参数1（Hibernate）：False → 睡眠（非休眠）
        - 参数2（ForceCritical）：False → 允许应用程序取消
        - 参数3（DisableWakeEvent）：False → 允许唤醒事件

        禁止使用 ForceCritical=True，否则硬件可能无法正常唤醒。
        """
        result = ctypes.windll.powrprof.SetSuspendState(False, False, False)
        if not result:
            raise RuntimeError("SetSuspendState 返回失败，可能被其他程序阻止")
