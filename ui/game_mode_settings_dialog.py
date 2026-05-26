# --------------------------------------------------------------------------
# 文件：ui/game_mode_settings_dialog.py
# 用途：游戏模式设置弹窗——启用/禁用、设置游戏结束后倒计时时长
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QCheckBox, QDialogButtonBox,
)


class GameModeSettingsDialog(QDialog):
    """游戏模式设置弹窗"""

    def __init__(self, enabled: bool, countdown_secs: int, parent=None):
        """
        参数：
            enabled:         当前是否启用游戏模式
            countdown_secs:  游戏结束后倒计时秒数
        """
        super().__init__(parent)
        self.setWindowTitle("游戏模式设置")
        self.setFixedSize(340, 160)

        self._enabled = enabled
        self._countdown_secs = countdown_secs
        self._setup_ui()

    def _setup_ui(self):
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- 启用复选框 ----
        self.enable_cb = QCheckBox("启用游戏模式")
        self.enable_cb.setChecked(self._enabled)
        self.enable_cb.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_cb)

        # ---- 倒计时设置 ----
        countdown_layout = QHBoxLayout()
        countdown_layout.addWidget(QLabel("游戏结束后"))

        self.countdown_spin = QSpinBox()
        self.countdown_spin.setRange(10, 600)
        self.countdown_spin.setValue(self._countdown_secs)
        self.countdown_spin.setSuffix(" 秒")
        self.countdown_spin.setEnabled(self._enabled)
        countdown_layout.addWidget(self.countdown_spin)

        countdown_layout.addWidget(QLabel("后自动执行任务"))
        countdown_layout.addStretch()
        layout.addLayout(countdown_layout)

        # ---- 提示文字 ----
        note = QLabel("注：游戏运行时倒计时归零将自动推迟 15 分钟")
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
        """启用/禁用时同步锁定倒计时旋钮"""
        self.countdown_spin.setEnabled(checked)

    # ======================== 外部接口 ========================

    def is_enabled(self) -> bool:
        return self.enable_cb.isChecked()

    def get_countdown_seconds(self) -> int:
        return self.countdown_spin.value()
