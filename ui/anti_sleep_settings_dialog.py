# --------------------------------------------------------------------------
# 文件：ui/anti_sleep_settings_dialog.py
# 用途：防休眠设置弹窗——启用/禁用、设置是否阻止显示器关闭
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QDialogButtonBox, QFrame,
)
from PySide6.QtCore import Qt


class AntiSleepSettingsDialog(QDialog):
    """防休眠设置弹窗"""

    def __init__(self, enabled: bool, block_display: bool, parent=None):
        """
        参数：
            enabled:       当前是否启用防休眠
            block_display: 当前是否同时阻止显示器熄灭
        """
        super().__init__(parent)
        self.setWindowTitle("防休眠设置")
        self.setFixedSize(380, 220)

        self._enabled = enabled
        self._block_display = block_display
        self._setup_ui()

    def _setup_ui(self):
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # ---- 说明文字 ----
        desc = QLabel("在倒计时任务运行期间阻止系统进入睡眠或锁屏状态，\n"
                      "确保关机/重启等任务能正常执行。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #495057; font-size: 12px;")
        layout.addWidget(desc)

        # ---- 分隔线 ----
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #DDE3E9;")
        layout.addWidget(line)

        # ---- 启用复选框 ----
        self.enable_cb = QCheckBox("启用防休眠保护")
        self.enable_cb.setChecked(self._enabled)
        self.enable_cb.toggled.connect(self._on_enable_toggled)
        self.enable_cb.setStyleSheet("font-size: 13px; font-weight: bold; color: #343A40;")
        layout.addWidget(self.enable_cb)

        # ---- 阻止显示器关闭（子选项） ----
        self.display_cb = QCheckBox("同时阻止显示器自动熄灭")
        self.display_cb.setChecked(self._block_display)
        self.display_cb.setEnabled(self._enabled)
        self.display_cb.setStyleSheet("font-size: 12px; color: #495057; padding-left: 24px;")
        layout.addWidget(self.display_cb)

        # ---- 提示文字 ----
        note = QLabel("注：阻止显示器熄灭会增加耗电，适用于需要保持屏幕亮起的场景")
        note.setWordWrap(True)
        note.setStyleSheet("color: #868E96; font-size: 10px; padding-left: 24px;")
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
        """启用/禁用时同步锁定子选项"""
        self.display_cb.setEnabled(checked)

    # ======================== 外部接口 ========================

    def is_enabled(self) -> bool:
        """防休眠是否启用"""
        return self.enable_cb.isChecked()

    def get_block_display(self) -> bool:
        """是否阻止显示器关闭"""
        return self.display_cb.isChecked()
