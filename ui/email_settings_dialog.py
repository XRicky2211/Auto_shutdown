# --------------------------------------------------------------------------
# 文件：ui/email_settings_dialog.py
# 用途：邮件通知设置弹窗——配置 SMTP 服务器与收发件人
# --------------------------------------------------------------------------

import threading
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QCheckBox, QDialogButtonBox, QPushButton,
    QMessageBox, QSpinBox, QFormLayout,
)
from PySide6.QtCore import Qt, QTimer, Signal

from core.notification.email_sender import EmailSender


class EmailSettingsDialog(QDialog):
    """邮件通知设置弹窗"""

    _test_finished = Signal(bool, str)  # 跨线程信号：(success, message)
    _conn_check_finished = Signal(bool)  # 后台连通性检测结果
    _pending_done = Signal()  # 关闭测试中弹窗

    def __init__(self, enabled: bool, smtp_server: str, port: int,
                 user: str, password: str, to_email: str, parent=None):
        """
        参数：
            enabled:       是否启用邮件通知
            smtp_server:   SMTP 服务器地址
            port:          SMTP 端口
            user:          发件邮箱
            password:      SMTP 授权码
            to_email:      收件邮箱
        """
        super().__init__(parent)
        self.setWindowTitle("邮件通知设置")
        self.setFixedSize(450, 420)

        self._enabled = enabled
        self._smtp_server = smtp_server
        self._port = port
        self._user = user
        self._password = password
        self._to_email = to_email
        self._connected = False

        self._setup_ui()
        self._test_finished.connect(self._show_test_result)
        self._conn_check_finished.connect(self._set_connected)
        self._pending_done.connect(self._close_pending)
        self._pending = None
        # 弹窗打开后后台检测连通性
        QTimer.singleShot(100, self._check_connection_background)

    def _setup_ui(self):
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # ---- 启用复选框 ----
        self.enable_cb = QCheckBox("启用邮件通知")
        self.enable_cb.setChecked(self._enabled)
        self.enable_cb.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_cb)

        # ---- 表单布局 ----
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # SMTP 服务器
        self.smtp_server_edit = QLineEdit(self._smtp_server)
        self.smtp_server_edit.setPlaceholderText("smtp.163.com")
        self.smtp_server_edit.setEnabled(self._enabled)
        form_layout.addRow("SMTP 服务器：", self.smtp_server_edit)

        # 端口
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(self._port)
        self.port_spin.setEnabled(self._enabled)
        form_layout.addRow("端口：", self.port_spin)

        # 发件邮箱
        self.user_edit = QLineEdit(self._user)
        self.user_edit.setPlaceholderText("your-email@163.com")
        self.user_edit.setEnabled(self._enabled)
        form_layout.addRow("发件邮箱：", self.user_edit)

        # SMTP 授权码
        self.password_edit = QLineEdit(self._password)
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("请输入 SMTP 授权码")
        self.password_edit.setEnabled(self._enabled)
        form_layout.addRow("SMTP 授权码：", self.password_edit)

        # 收件邮箱
        self.to_email_edit = QLineEdit(self._to_email)
        self.to_email_edit.setPlaceholderText("recipient@example.com")
        self.to_email_edit.setEnabled(self._enabled)
        form_layout.addRow("收件邮箱：", self.to_email_edit)

        layout.addLayout(form_layout)

        # ---- 测试按钮 ----
        test_layout = QHBoxLayout()
        test_layout.addStretch()

        self.test_conn_btn = QPushButton("测试连接")
        self.test_conn_btn.setEnabled(self._enabled)
        self.test_conn_btn.clicked.connect(self._on_test_connection)
        test_layout.addWidget(self.test_conn_btn)

        self.test_send_btn = QPushButton("发送测试邮件")
        self.test_send_btn.setEnabled(self._enabled)
        self.test_send_btn.clicked.connect(self._on_send_test)
        test_layout.addWidget(self.test_send_btn)

        layout.addLayout(test_layout)

        # ---- 连接状态 ----
        self.conn_status_label = QLabel("检测中...")
        self.conn_status_label.setAlignment(Qt.AlignCenter)
        self.conn_status_label.setStyleSheet("font-size: 12px; color: #868E96;")
        layout.addWidget(self.conn_status_label)

        # ---- 提示文字 ----
        note = QLabel(
            "提示：\n"
            "• 163/QQ 邮箱等需要在设置中开启 SMTP 服务并获取授权码\n"
            "• 授权码不是邮箱登录密码，请在邮箱安全设置中获取\n"
            "• 仅支持 SSL 加密连接（默认端口 465）"
        )
        note.setStyleSheet("color: #868E96; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()

        # ---- 确定 / 取消 ----
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("确认")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ======================== 内部方法 ========================

    def _check_connection_background(self):
        """后台检测连通性，更新状态标签"""
        if not self._enabled or not self._user:
            self._connected = False
            self._update_conn_label()
            return

        self.conn_status_label.setText("检测中...")
        self.conn_status_label.setStyleSheet("font-size: 12px; color: #868E96;")

        def _check():
            sender = EmailSender(
                self._smtp_server, self._port, self._user,
                self._password, self._to_email,
            )
            ok = sender.test_login()
            self._conn_check_finished.emit(ok)

        threading.Thread(target=_check, daemon=True).start()

    def _set_connected(self, ok: bool):
        """（主线程）更新连接状态"""
        self._connected = ok
        self._update_conn_label()

    def _update_conn_label(self):
        """刷新连接状态标签"""
        if not self._enabled or not self._user:
            self.conn_status_label.setText("未配置 SMTP")
            self.conn_status_label.setStyleSheet("font-size: 12px; color: #868E96;")
        elif self._connected:
            self.conn_status_label.setText("SMTP 连接状态：已联通")
            self.conn_status_label.setStyleSheet("font-size: 12px; color: #2B8A3E; font-weight: bold;")
        else:
            self.conn_status_label.setText("SMTP 连接状态：未联通")
            self.conn_status_label.setStyleSheet("font-size: 12px; color: #C92A2A; font-weight: bold;")

    def _on_enable_toggled(self, checked: bool):
        """启用/禁用时联动输入控件状态"""
        self.smtp_server_edit.setEnabled(checked)
        self.port_spin.setEnabled(checked)
        self.user_edit.setEnabled(checked)
        self.password_edit.setEnabled(checked)
        self.to_email_edit.setEnabled(checked)
        self.test_conn_btn.setEnabled(checked)
        self.test_send_btn.setEnabled(checked)
        if checked:
            self._check_connection_background()
        else:
            self._connected = False
            self._update_conn_label()

    def _on_test_connection(self):
        """测试 SMTP 连接（后台线程执行）"""
        smtp_server = self.smtp_server_edit.text().strip()
        port = self.port_spin.value()
        user = self.user_edit.text().strip()
        password = self.password_edit.text().strip()
        to_email = self.to_email_edit.text().strip()

        if not smtp_server or not user or not password or not to_email:
            QMessageBox.warning(self, "提示", "请先填写完整的 SMTP 配置")
            return

        self._pending = QMessageBox(
            QMessageBox.Information, "测试中", "正在测试连接，请稍候...",
            QMessageBox.NoButton, self,
        )
        self._pending.setStandardButtons(QMessageBox.NoButton)

        sender = EmailSender(smtp_server, port, user, password, to_email)

        def _test():
            success, msg = sender.test_connection()
            self._pending_done.emit()
            self._test_finished.emit(success, msg)
            if success:
                self._conn_check_finished.emit(True)

        threading.Thread(target=_test, daemon=True).start()
        self._pending.exec()
        self._pending = None

    def _close_pending(self):
        """关闭测试中弹窗（主线程）"""
        if self._pending:
            # 标记为 NoButton 时用 reject() 或 done(0) 均可
            self._pending.done(0)

    def _show_test_result(self, success: bool, message: str):
        """显示测试结果（在主线程调用）"""
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.warning(self, "失败", message)

    def _on_send_test(self):
        """发送测试邮件（后台线程执行）"""
        smtp_server = self.smtp_server_edit.text().strip()
        port = self.port_spin.value()
        user = self.user_edit.text().strip()
        password = self.password_edit.text().strip()
        to_email = self.to_email_edit.text().strip()

        if not smtp_server or not user or not password or not to_email:
            QMessageBox.warning(self, "提示", "请先填写完整的 SMTP 配置")
            return

        self._pending = QMessageBox(
            QMessageBox.Information, "发送中", "正在发送测试邮件，请稍候...",
            QMessageBox.NoButton, self,
        )
        self._pending.setStandardButtons(QMessageBox.NoButton)

        sender = EmailSender(smtp_server, port, user, password, to_email)

        def _send():
            success, msg = sender.send_test_email()
            self._pending_done.emit()
            self._test_finished.emit(success, msg)

        threading.Thread(target=_send, daemon=True).start()
        self._pending.exec()
        self._pending = None

    # ======================== 外部接口 ========================

    def is_enabled(self) -> bool:
        return self.enable_cb.isChecked()

    def get_smtp_server(self) -> str:
        return self.smtp_server_edit.text().strip()

    def get_port(self) -> int:
        return self.port_spin.value()

    def get_user(self) -> str:
        return self.user_edit.text().strip()

    def get_password(self) -> str:
        return self.password_edit.text().strip()

    def get_to_email(self) -> str:
        return self.to_email_edit.text().strip()
