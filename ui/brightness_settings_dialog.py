# --------------------------------------------------------------------------
# 文件：ui/brightness_settings_dialog.py
# 用途：亮度控制子弹窗 — 设置 AC/电池 两档亮度值与启用开关
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QCheckBox, QDialogButtonBox,
)
from PySide6.QtCore import Qt


class BrightnessSettingsDialog(QDialog):
    """亮度控制设置子弹窗"""

    def __init__(self, enabled: bool, ac_level: int, battery_level: int,
                 parent=None):
        """
        参数：
            enabled:       是否启用亮度自动调节
            ac_level:      接通电源时的亮度值（0-100）
            battery_level: 使用电池时的亮度值（0-100）
        """
        super().__init__(parent)
        self.setWindowTitle("亮度控制设置")
        self.setFixedSize(420, 260)

        self._enabled = enabled
        self._ac_level = ac_level
        self._battery_level = battery_level
        self._setup_ui()

    def _setup_ui(self):
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- 启用复选框 ----
        self.enable_cb = QCheckBox("启用亮度自动调节")
        self.enable_cb.setChecked(self._enabled)
        self.enable_cb.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_cb)

        # ---- AC 电源亮度 ----
        ac_label = QLabel("接通电源时亮度：")
        ac_label.setStyleSheet("color: #343A40; font-weight: bold;")
        layout.addWidget(ac_label)

        ac_row = QHBoxLayout()
        ac_row.setSpacing(10)

        self.ac_slider = QSlider(Qt.Horizontal)
        self.ac_slider.setRange(10, 100)
        self.ac_slider.setValue(self._ac_level)
        self.ac_slider.setEnabled(self._enabled)
        self.ac_slider.valueChanged.connect(self._on_ac_changed)
        ac_row.addWidget(self.ac_slider)

        self.ac_value_label = QLabel(f"{self._ac_level}%")
        self.ac_value_label.setFixedWidth(40)
        self.ac_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.ac_value_label.setStyleSheet("color: #339AF0; font-weight: bold;")
        ac_row.addWidget(self.ac_value_label)

        layout.addLayout(ac_row)

        # ---- 电池供电亮度 ----
        battery_label = QLabel("使用电池时亮度：")
        battery_label.setStyleSheet("color: #343A40; font-weight: bold;")
        layout.addWidget(battery_label)

        battery_row = QHBoxLayout()
        battery_row.setSpacing(10)

        self.battery_slider = QSlider(Qt.Horizontal)
        self.battery_slider.setRange(10, 100)
        self.battery_slider.setValue(self._battery_level)
        self.battery_slider.setEnabled(self._enabled)
        self.battery_slider.valueChanged.connect(self._on_battery_changed)
        battery_row.addWidget(self.battery_slider)

        self.battery_value_label = QLabel(f"{self._battery_level}%")
        self.battery_value_label.setFixedWidth(40)
        self.battery_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.battery_value_label.setStyleSheet("color: #E8590C; font-weight: bold;")
        battery_row.addWidget(self.battery_value_label)

        layout.addLayout(battery_row)

        # ---- 提示文字 ----
        note = QLabel(
            "提示：程序启动时根据当前电源状态自动设置亮度；\n"
            "运行期间检测到电源插拔时也会自动切换亮度。\n"
            "仅支持笔记本内置屏幕，外接显示器不生效。"
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

    def _on_enable_toggled(self, checked: bool):
        """启用/禁用时联动滑块状态"""
        self.ac_slider.setEnabled(checked)
        self.battery_slider.setEnabled(checked)

    def _on_ac_changed(self, value: int):
        """AC 滑块变化时更新标签"""
        self.ac_value_label.setText(f"{value}%")

    def _on_battery_changed(self, value: int):
        """电池滑块变化时更新标签"""
        self.battery_value_label.setText(f"{value}%")

    # ======================== 外部接口 ========================

    def is_enabled(self) -> bool:
        return self.enable_cb.isChecked()

    def get_ac_level(self) -> int:
        return self.ac_slider.value()

    def get_battery_level(self) -> int:
        return self.battery_slider.value()
