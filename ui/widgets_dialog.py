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


class WidgetsDialog(QDialog):
    """小组件功能清单弹窗（可扩展多个小功能区）"""

    def __init__(self, brightness_enabled: bool, brightness_ac: int,
                 brightness_battery: int, parent=None):
        """
        参数：
            brightness_enabled:  亮度控制是否启用
            brightness_ac:       接通电源亮度值
            brightness_battery:  使用电池亮度值
        """
        super().__init__(parent)
        self.setWindowTitle("小组件")
        self.setMinimumSize(420, 180)

        self._brightness_enabled = brightness_enabled
        self._brightness_ac = brightness_ac
        self._brightness_battery = brightness_battery

        # 标记亮度设置是否有变更
        self._brightness_changed = False

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
        if self._brightness_enabled:
            self.status_label.setText(
                f"亮度控制已启用 ｜  AC: {self._brightness_ac}%  ｜  电池: {self._brightness_battery}%"
            )
        else:
            self.status_label.setText("亮度控制已禁用")

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
