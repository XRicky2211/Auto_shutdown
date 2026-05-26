# --------------------------------------------------------------------------
# 文件：ui/reminder_settings_dialog.py
# 用途：关机前提醒设置弹窗——添加/删除提醒时间、设置推迟按钮时长
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QPushButton, QListWidget, QDialogButtonBox,
)


class ReminderSettingsDialog(QDialog):
    """关机前提醒设置弹窗"""

    def __init__(self, reminder_times: list, delay_minutes: int, parent=None):
        """
        参数：
            reminder_times: 已有的提醒时间列表（单位：分钟）
            delay_minutes:  当前的推迟按钮时长
        """
        super().__init__(parent)
        self.setWindowTitle("关机前提醒设置")
        self.setFixedSize(340, 300)

        # 拷贝一份，避免直接修改主窗口的数据（取消时不影响原数据）
        self._reminder_times = reminder_times.copy()
        self._delay_minutes = delay_minutes

        self._setup_ui()

    def _setup_ui(self):
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ---- 添加提醒 ----
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("关机前"))
        self.reminder_spin = QSpinBox()
        self.reminder_spin.setRange(1, 9999)
        self.reminder_spin.setValue(5)
        self.reminder_spin.setSuffix(" 分钟")
        add_row.addWidget(self.reminder_spin)
        add_row.addWidget(QLabel("弹窗提醒"))

        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_reminder)
        add_row.addWidget(add_btn)
        add_row.addStretch()
        layout.addLayout(add_row)

        # ---- 已设提醒列表 ----
        self.reminder_list = QListWidget()
        layout.addWidget(self.reminder_list)

        del_btn = QPushButton("删除选中提醒")
        del_btn.clicked.connect(self._delete_reminder)
        layout.addWidget(del_btn)

        # ---- 推迟时长设置 ----
        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("推迟按钮时长："))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(1, 999)
        self.delay_spin.setValue(self._delay_minutes)
        self.delay_spin.setSuffix(" 分钟")
        delay_row.addWidget(self.delay_spin)
        delay_row.addStretch()
        layout.addLayout(delay_row)

        # ---- 确定 / 取消 ----
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("确认")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 刷新列表显示
        self._refresh_list()

    # ======================== 内部方法 ========================

    def _add_reminder(self):
        """添加一条提醒"""
        minutes = self.reminder_spin.value()
        if minutes not in self._reminder_times:
            self._reminder_times.append(minutes)
            self._reminder_times.sort()
            self._refresh_list()

    def _delete_reminder(self):
        """删除选中的提醒"""
        current = self.reminder_list.currentItem()
        if not current:
            return
        text = current.text()
        try:
            minutes = int(text.replace("关机前 ", "").replace(" 分钟提醒", ""))
            if minutes in self._reminder_times:
                self._reminder_times.remove(minutes)
                self._refresh_list()
        except ValueError:
            pass

    def _refresh_list(self):
        """刷新提醒列表显示"""
        self.reminder_list.clear()
        for t in self._reminder_times:
            self.reminder_list.addItem(f"关机前 {t} 分钟提醒")

    # ======================== 外部接口 ========================

    def get_reminder_times(self) -> list:
        return self._reminder_times

    def get_delay_minutes(self) -> int:
        return self.delay_spin.value()
