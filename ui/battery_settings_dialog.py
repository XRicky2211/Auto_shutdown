# --------------------------------------------------------------------------
# 文件：ui/battery_settings_dialog.py
# 用途：低电量自动关机设置弹窗——启用/禁用、设置阈值
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QCheckBox, QDialogButtonBox,
)


class BatterySettingsDialog(QDialog):
    """低电量自动关机设置弹窗"""

    def __init__(self, enabled: bool, threshold: int, parent=None):
        """
        参数：
            enabled:   当前是否启用低电量关机
            threshold: 当前阈值（百分比）
        """
        super().__init__(parent)
        self.setWindowTitle("低电量设置")
        self.setFixedSize(340, 160)

        self._enabled = enabled
        self._threshold = threshold
        self._setup_ui()

    def _setup_ui(self):
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- 启用复选框 ----
        self.enable_cb = QCheckBox("启用低电量自动关机")
        self.enable_cb.setChecked(self._enabled)
        self.enable_cb.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_cb)

        # ---- 阈值设置 ----
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("当电量低于"))

        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 100)
        self.threshold_spin.setValue(self._threshold)
        self.threshold_spin.setSuffix(" %")
        self.threshold_spin.setEnabled(self._enabled)
        threshold_layout.addWidget(self.threshold_spin)

        threshold_layout.addWidget(QLabel("且未接通电源时启动倒计时关机"))
        threshold_layout.addStretch()
        layout.addLayout(threshold_layout)

        # ---- 提示文字 ----
        note = QLabel("注：系统每 3 分钟检测一次电池状态，低于阈值时弹出60秒倒计时提醒")
        note.setStyleSheet("color: #868E96; font-size: 11px;")
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
        """启用/禁用时同步锁定阈值旋钮"""
        self.threshold_spin.setEnabled(checked)

    # ======================== 外部接口 ========================

    def is_enabled(self) -> bool:
        return self.enable_cb.isChecked()

    def get_threshold(self) -> int:
        return self.threshold_spin.value()
