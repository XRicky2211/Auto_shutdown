# --------------------------------------------------------------------------
# 文件：ui/widgets_dialog.py
# 用途：小组件功能清单弹窗 — 列出所有小组件功能入口
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from ui.brightness_settings_dialog import BrightnessSettingsDialog
from ui.email_settings_dialog import EmailSettingsDialog


class WidgetsDialog(QDialog):
    """小组件功能清单弹窗（可扩展多个小功能区）"""

    def __init__(self, brightness_enabled: bool, brightness_ac: int,
                 brightness_battery: int, email_enabled: bool,
                 email_config: dict, parent=None):
        """
        参数：
            brightness_enabled:  亮度控制是否启用
            brightness_ac:       接通电源亮度值
            brightness_battery:  使用电池亮度值
            email_enabled:       邮件通知是否启用
            email_config:        邮件配置字典
        """
        super().__init__(parent)
        self.setWindowTitle("小组件")
        self.setMinimumSize(420, 280)

        self._brightness_enabled = brightness_enabled
        self._brightness_ac = brightness_ac
        self._brightness_battery = brightness_battery

        # ---- 邮件通知 ----
        self._email_enabled = email_enabled
        self._email_config = email_config.copy()

        # 标记变更
        self._brightness_changed = False
        self._email_changed = False

        self._setup_ui()
        self._apply_stylesheet()

    def _setup_ui(self):
        """创建界面 — 功能清单列表"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ---- 标题 ----
        title = QLabel("小组件")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #339AF0;
            padding-bottom: 4px;
        """)
        layout.addWidget(title)

        # ---- 亮度控制卡片 ----
        card = QFrame()
        card.setObjectName("widgetCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(12)

        # 左侧：图标 + 文字
        icon_label = QLabel("☀")
        icon_label.setStyleSheet("font-size: 24px; color: #FD7E14;")
        card_layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        name_label = QLabel("亮度控制")
        name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #343A40;")

        desc_label = QLabel("根据电源状态自动调节屏幕亮度")
        desc_label.setStyleSheet("font-size: 11px; color: #868E96;")
        desc_label.setWordWrap(True)

        text_layout.addWidget(name_label)
        text_layout.addWidget(desc_label)
        card_layout.addLayout(text_layout, 1)

        # 右侧：设置按钮
        self.brightness_btn = QPushButton("设置")
        self.brightness_btn.setObjectName("widgetSettingBtn")
        self.brightness_btn.clicked.connect(self._open_brightness_settings)
        card_layout.addWidget(self.brightness_btn)

        # 卡片阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 2)
        card.setGraphicsEffect(shadow)

        layout.addWidget(card)

        # ---- 邮件通知卡片 ----
        email_card = QFrame()
        email_card.setObjectName("widgetCard")
        email_card_layout = QHBoxLayout(email_card)
        email_card_layout.setContentsMargins(16, 12, 16, 12)
        email_card_layout.setSpacing(12)

        # 左侧：图标 + 文字
        email_icon_label = QLabel("📧")
        email_icon_label.setStyleSheet("font-size: 24px; color: #12B886;")
        email_card_layout.addWidget(email_icon_label)

        email_text_layout = QVBoxLayout()
        email_text_layout.setSpacing(2)

        email_name_label = QLabel("邮件通知")
        email_name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #343A40;")

        email_desc_label = QLabel("关机/重启时发送邮件通知")
        email_desc_label.setStyleSheet("font-size: 11px; color: #868E96;")
        email_desc_label.setWordWrap(True)

        email_text_layout.addWidget(email_name_label)
        email_text_layout.addWidget(email_desc_label)
        email_card_layout.addLayout(email_text_layout, 1)

        # 右侧：设置按钮
        self.email_btn = QPushButton("设置")
        self.email_btn.setObjectName("widgetSettingBtn")
        self.email_btn.clicked.connect(self._open_email_settings)
        email_card_layout.addWidget(self.email_btn)

        # 卡片阴影
        email_shadow = QGraphicsDropShadowEffect()
        email_shadow.setBlurRadius(16)
        email_shadow.setColor(QColor(0, 0, 0, 15))
        email_shadow.setOffset(0, 2)
        email_card.setGraphicsEffect(email_shadow)

        layout.addWidget(email_card)

        # ---- 预留：更多小组件可在此处追加卡片 ----

        layout.addStretch()

        # 状态摘要
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #868E96; font-size: 11px;")
        self._update_status_label()
        layout.addWidget(self.status_label)

        # ---- 完成按钮 ----
        done_btn = QPushButton("完成")
        done_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4DABF7, stop:1 #339AF0);
                border: none;
                border-radius: 8px;
                padding: 10px 0;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #339AF0, stop:1 #228BE6);
            }
        """)
        done_btn.clicked.connect(self.accept)
        layout.addWidget(done_btn)

    def _apply_stylesheet(self):
        """应用弹窗样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #F8F9FA;
            }
            QFrame#widgetCard {
                background-color: #FFFFFF;
                border: 1px solid #DDE3E9;
                border-radius: 10px;
            }
            QPushButton#widgetSettingBtn {
                background: transparent;
                border: 1px solid #339AF0;
                border-radius: 6px;
                padding: 6px 14px;
                color: #339AF0;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#widgetSettingBtn:hover {
                background: #339AF0;
                color: #FFFFFF;
            }
        """)

    def _update_status_label(self):
        """刷新底部状态文字"""
        parts = []
        if self._brightness_enabled:
            parts.append(f"亮度控制已启用 ｜ AC: {self._brightness_ac}% ｜ 电池: {self._brightness_battery}%")
        else:
            parts.append("亮度控制已禁用")

        if self._email_enabled:
            parts.append("邮件通知已启用")
        else:
            parts.append("邮件通知已禁用")

        self.status_label.setText(" ｜ ".join(parts))

    # ======================== 打开亮度设置 ========================

    def _open_brightness_settings(self):
        """打开亮度控制设置子弹窗"""
        dialog = BrightnessSettingsDialog(
            self._brightness_enabled,
            self._brightness_ac,
            self._brightness_battery,
            self,
        )
        if dialog.exec() == QDialog.Accepted:
            new_enabled = dialog.is_enabled()
            new_ac = dialog.get_ac_level()
            new_battery = dialog.get_battery_level()

            changed = (
                new_enabled != self._brightness_enabled
                or new_ac != self._brightness_ac
                or new_battery != self._brightness_battery
            )
            if changed:
                self._brightness_changed = True
                self._brightness_enabled = new_enabled
                self._brightness_ac = new_ac
                self._brightness_battery = new_battery

            self._update_status_label()

    # ======================== 打开邮件设置 ========================

    def _open_email_settings(self):
        """打开邮件通知设置子弹窗"""
        dialog = EmailSettingsDialog(
            self._email_enabled,
            self._email_config.get("smtp_server", "smtp.163.com"),
            self._email_config.get("port", 465),
            self._email_config.get("user", ""),
            self._email_config.get("password", ""),
            self._email_config.get("to_email", ""),
            self,
        )
        if dialog.exec() == QDialog.Accepted:
            new_enabled = dialog.is_enabled()
            new_smtp = dialog.get_smtp_server()
            new_port = dialog.get_port()
            new_user = dialog.get_user()
            new_password = dialog.get_password()
            new_to = dialog.get_to_email()

            changed = (
                new_enabled != self._email_enabled
                or new_smtp != self._email_config.get("smtp_server")
                or new_port != self._email_config.get("port")
                or new_user != self._email_config.get("user")
                or new_password != self._email_config.get("password")
                or new_to != self._email_config.get("to_email")
            )
            if changed:
                self._email_changed = True
                self._email_enabled = new_enabled
                self._email_config = {
                    "smtp_server": new_smtp,
                    "port": new_port,
                    "user": new_user,
                    "password": new_password,
                    "to_email": new_to,
                }

            self._update_status_label()

    # ======================== 外部接口 ========================

    def is_brightness_changed(self) -> bool:
        """亮度设置是否有变更"""
        return self._brightness_changed

    def get_brightness_enabled(self) -> bool:
        return self._brightness_enabled

    def get_brightness_ac(self) -> int:
        return self._brightness_ac

    def get_brightness_battery(self) -> int:
        return self._brightness_battery

    def is_email_changed(self) -> bool:
        """邮件设置是否有变更"""
        return self._email_changed

    def get_email_enabled(self) -> bool:
        return self._email_enabled

    def get_email_config(self) -> dict:
        return self._email_config.copy()
