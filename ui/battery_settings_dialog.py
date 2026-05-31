# --------------------------------------------------------------------------
# 文件：ui/battery_settings_dialog.py
# 用途：低电量自动关机设置弹窗——启用/禁用、两级阈值设置
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QCheckBox, QDialogButtonBox,
)


class BatterySettingsDialog(QDialog):
    """低电量自动关机设置弹窗（两级阈值）"""

    def __init__(self, enabled: bool, warning_threshold: int,
                 critical_threshold: int, parent=None):
        """
        参数：
            enabled:            当前是否启用低电量关机
            warning_threshold:  警告级阈值（百分比）
            critical_threshold: 临界级阈值（百分比）
        """
        super().__init__(parent)
        self.setWindowTitle("低电量设置")
        self.setFixedSize(380, 200)

        self._enabled = enabled
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._setup_ui()

    def _setup_ui(self):
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ---- 启用复选框 ----
        self.enable_cb = QCheckBox("启用低电量自动关机")
        self.enable_cb.setChecked(self._enabled)
        self.enable_cb.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_cb)

        # ---- 警告阈值 ----
        warning_layout = QHBoxLayout()

        warning_label = QLabel("警告阈值：低于")
        warning_label.setStyleSheet("color: #E8590C; font-weight: bold;")
        warning_layout.addWidget(warning_label)

        self.warning_spin = QSpinBox()
        self.warning_spin.setRange(2, 99)
        self.warning_spin.setValue(self._warning_threshold)
        self.warning_spin.setSuffix(" %")
        self.warning_spin.setEnabled(self._enabled)
        self.warning_spin.valueChanged.connect(self._on_warning_changed)
        warning_layout.addWidget(self.warning_spin)

        warning_layout.addWidget(QLabel("时发出提醒"))
        warning_layout.addStretch()
        layout.addLayout(warning_layout)

        # ---- 临界阈值 ----
        critical_layout = QHBoxLayout()

        critical_label = QLabel("临界阈值：低于")
        critical_label.setStyleSheet("color: #E03131; font-weight: bold;")
        critical_layout.addWidget(critical_label)

        self.critical_spin = QSpinBox()
        self.critical_spin.setRange(1, 98)
        self.critical_spin.setValue(self._critical_threshold)
        self.critical_spin.setSuffix(" %")
        self.critical_spin.setEnabled(self._enabled)
        self.critical_spin.valueChanged.connect(self._on_critical_changed)
        critical_layout.addWidget(self.critical_spin)

        critical_layout.addWidget(QLabel("时自动进入紧急模式"))
        critical_layout.addStretch()
        layout.addLayout(critical_layout)

        # ---- 提示文字 ----
        note = QLabel(
            "注：两级检测，电量下降至临界阈值时触发自动关机倒计时。\n"
            "系统每 3 分钟检测一次，接近阈值时自动加快检测频率。"
        )
        note.setStyleSheet("color: #868E96; font-size: 11px;")
        layout.addWidget(note)

        layout.addStretch()

        # ---- 确定 / 取消 ----
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("确认")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ======================== 内部方法 ========================

    def _on_enable_toggled(self, checked: bool):
        """启用/禁用时同步锁定阈值旋钮"""
        self.warning_spin.setEnabled(checked)
        self.critical_spin.setEnabled(checked)

    def _on_warning_changed(self, value: int):
        """警告阈值改变时，确保临界阈值 < 警告阈值"""
        if self.critical_spin.value() >= value:
            self.critical_spin.setValue(max(1, value - 1))

    def _on_critical_changed(self, value: int):
        """临界阈值改变时，确保警告阈值 > 临界阈值"""
        if self.warning_spin.value() <= value:
            self.warning_spin.setValue(min(99, value + 1))

    def _validate_and_accept(self):
        """校验通过后接受"""
        w = self.warning_spin.value()
        c = self.critical_spin.value()
        if w <= c:
            # 防御性：强制修正（正常情况下联动逻辑已确保 w > c）
            self.warning_spin.setValue(c + 1)
        self.accept()

    # ======================== 外部接口 ========================

    def is_enabled(self) -> bool:
        return self.enable_cb.isChecked()

    def get_warning_threshold(self) -> int:
        return self.warning_spin.value()

    def get_critical_threshold(self) -> int:
        return self.critical_spin.value()

    # 向后兼容接口（旧代码调用）
    def get_threshold(self) -> int:
        return self.warning_spin.value()
