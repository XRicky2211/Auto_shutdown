# --------------------------------------------------------------------------
# 文件：core/notification/email_sender.py
# 用途：邮件通知发送模块——关机时发送通知邮件
# 原则：幂等发送 + 安全失败 + 可观测性
# --------------------------------------------------------------------------

import json
import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _data_dir() -> str:
    """获取数据目录路径（与 settings.json 同级）"""
    if getattr(sys, "frozen", False):
        return os.path.join(os.environ["APPDATA"], "AutoShutdownHelper")
    # 开发环境：project_root 与 core/ 同级
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


_SENT_IDS_PATH = os.path.join(_data_dir(), "sent_emails.json")
_ERROR_LOG_PATH = os.path.join(_data_dir(), "email_error.log")


class EmailSender:
    """邮件通知发送器

    职责：
    - 发送关机/重启/注销通知邮件
    - 幂等：同一 task_id 只发送一次（持久化到 sent_emails.json）
    - 完全 try/except 包裹，安全失败不影响关机
    - SMTP 失败记录到 email_error.log
    - 支持 SSL SMTP（默认端口 465）
    """

    _sent_task_ids: set = None  # 类级持久化缓存，所有实例共享

    def __init__(self, smtp_server: str, port: int, user: str, password: str, to_email: str):
        """
        参数：
            smtp_server: SMTP 服务器地址（如 smtp.163.com）
            port: SMTP 端口（如 465）
            user: 发件邮箱地址
            password: SMTP 授权码（不是邮箱登录密码）
            to_email: 收件邮箱地址
        """
        self.smtp_server = smtp_server
        self.port = port
        self.user = user
        self.password = password
        self.to_email = to_email

        # 首次实例化时从磁盘加载已发送 task_id 列表
        if EmailSender._sent_task_ids is None:
            EmailSender._sent_task_ids = self._load_sent_ids()

    def send_shutdown_notice(self, task_type: str, time_str: str, task_id: str):
        """发送关机通知邮件（幂等 + 安全失败）

        参数：
            task_type: 任务类型 "shutdown" / "restart" / "logout"
            time_str: 触发时间字符串
            task_id: 唯一任务 ID，同一 task_id 只发送一次
        """
        if not self.user or not self.password or not self.to_email:
            return  # 配置不完整，静默跳过

        if task_id in EmailSender._sent_task_ids:
            return  # 已发送，幂等跳过

        try:
            self._send(task_type, time_str)
            # 发送成功后才记录 task_id
            EmailSender._sent_task_ids.add(task_id)
            self._save_sent_ids()
        except Exception as e:
            # 记录失败详情但不影响主流程
            self._log_error(task_type, task_id, str(e))

    def send_with_retry(self, task_type: str, time_str: str, task_id: str,
                        cause: str = "",
                        max_retries: int = 3, retry_delay: float = 3.0) -> bool:
        """带重试的邮件发送，返回是否发送成功

        参数：
            task_type:   任务类型
            time_str:    触发时间字符串
            task_id:     唯一任务 ID
            cause:       触发原因（倒计时结束/定时计划/每周计划/低电量）
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）

        返回：
            True  = 发送成功（或已发送过）
            False = 所有重试均失败
        """
        if not self.user or not self.password or not self.to_email:
            return False

        if task_id in EmailSender._sent_task_ids:
            return True

        for attempt in range(1, max_retries + 1):
            try:
                self._send(task_type, time_str, cause)
                EmailSender._sent_task_ids.add(task_id)
                self._save_sent_ids()
                return True
            except Exception as e:
                self._log_error(task_type, task_id,
                                f"第{attempt}次失败: {e}")
                if attempt < max_retries:
                    import time as _time
                    _time.sleep(retry_delay)

        return False

    def send_test_email(self) -> tuple[bool, str]:
        """发送一封真正的测试邮件（用于设置界面测试）

        返回：
            (success: bool, message: str)
        """
        if not self.user or not self.password or not self.to_email:
            return False, "请先填写完整的 SMTP 配置"

        try:
            subject = "[测试] 自动关机助手 - 测试邮件"

            body = """
            <html>
                <body>
                    <h3>自动关机助手 - 测试邮件</h3>
                    <p>这是一封测试邮件，表明邮件通知功能配置正确。</p>
                    <p style="color: #868E96; font-size: 12px;">
                        此邮件由 AutoShutdownHelper 自动发送，请勿回复。
                    </p>
                </body>
            </html>
            """

            msg = MIMEMultipart()
            msg["From"] = self.user
            msg["To"] = self.to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html", "utf-8"))

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_server, self.port, context=context, timeout=15) as server:
                server.login(self.user, self.password)
                server.send_message(msg)

            return True, "测试邮件发送成功，请检查收件箱"
        except Exception as e:
            return False, f"发送失败: {str(e)}"

    def test_login(self) -> bool:
        """完整检测 SMTP 连通性（连接 + 登录，不发送邮件）"""
        if not self.user or not self.password or not self.to_email:
            return False

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_server, self.port, context=context, timeout=10) as server:
                server.login(self.user, self.password)
            return True
        except Exception:
            return False

    def test_connection(self) -> tuple[bool, str]:
        """测试 SMTP 连接（用于设置界面测试）

        返回：
            (success: bool, message: str)
        """
        if not self.user or not self.password or not self.to_email:
            return False, "请先填写完整的 SMTP 配置"

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_server, self.port, context=context, timeout=10):
                pass  # 只连接不登录
            return True, "连接成功"
        except Exception as e:
            return False, f"连接失败: {str(e)}"

    # ======================== 内部实现 ========================

    def _load_sent_ids(self) -> set:
        """从磁盘加载已发送 task_id 列表"""
        try:
            with open(_SENT_IDS_PATH, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return set()

    def _save_sent_ids(self):
        """持久化已发送 task_id 列表到磁盘"""
        try:
            os.makedirs(_data_dir(), exist_ok=True)
            with open(_SENT_IDS_PATH, "w", encoding="utf-8") as f:
                json.dump(list(EmailSender._sent_task_ids), f, ensure_ascii=False)
        except OSError:
            pass

    def _log_error(self, task_type: str, task_id: str, error_msg: str):
        """记录 SMTP 发送失败到 error 日志"""
        try:
            os.makedirs(_data_dir(), exist_ok=True)
            with open(_ERROR_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                        f"task={task_type} id={task_id} error={error_msg}\n")
        except OSError:
            pass

    def _send(self, task_type: str, time_str: str, cause: str = ""):
        """实际发送邮件的内部方法"""
        task_names = {
            "shutdown": "关机",
            "restart": "重启",
            "logout": "注销",
            "sleep": "睡眠",
            "hibernate": "休眠",
        }
        task_name = task_names.get(task_type, task_type)

        # 根据触发原因构建不同的邮件主题和正文
        cause_labels = {
            "countdown": "倒计时结束",
            "schedule_once": "定时计划",
            "schedule_daily": "每日计划",
            "schedule_weekdays": "工作日计划",
            "schedule_weekends": "周末计划",
            "schedule_weekly": "每周计划",
            "low_battery": "低电量自动关机",
        }
        cause_label = cause_labels.get(cause, cause) if cause else "计划任务"

        subject = f"[{task_name}] 自动关机助手 - {cause_label}"

        body = f"""
        <html>
            <body>
                <h3>自动关机助手 - {task_name}通知</h3>
                <p>触发原因：<b>{cause_label}</b></p>
                <p>系统已于 <b>{time_str}</b> 执行 <b>{task_name}</b> 操作。</p>
                <br>
                <p style="color: #868E96; font-size: 12px;">
                    此邮件由 AutoShutdownHelper 自动发送，请勿回复。
                </p>
            </body>
        </html>
        """

        msg = MIMEMultipart()
        msg["From"] = self.user
        msg["To"] = self.to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.smtp_server, self.port, context=context, timeout=15) as server:
            server.login(self.user, self.password)
            server.send_message(msg)
