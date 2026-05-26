# --------------------------------------------------------------------------
# 文件：ui/timer_settings_dialog.py
# 用途：定时设置弹窗——选择"倒计时模式"或"定点定时模式"并输入具体时间
#       定点时间采用可编辑下拉框，支持键盘输入和鼠标点击选择
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSpinBox, QDialogButtonBox, QWidget,
    QPushButton, QButtonGroup,
)
from PySide6.QtCore import QTime

from ui.schedule_plan_dialog import SchedulePlanDialog, WEEKDAY_NAMES


PLAN_TYPE_LABELS = {
    "once": "仅一次",
    "daily": "每天定时",
    "weekdays": "工作日计划",
    "weekends": "周末计划",
    "weekly": "每周定时计划",
}


class TimerSettingsDialog(QDialog):
    """定时设置弹窗"""

    def __init__(self, plan: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("定时设置")
        self.setFixedSize(340, 240)
        self._plan = plan.copy() if plan else SchedulePlanDialog.default_plan()
        self._setup_ui()

    def _setup_ui(self):
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- 模式选择（并列按钮） ----
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("运行模式："))

        self.mode_group = QButtonGroup(self)
        self.countdown_btn = QPushButton("倒计时模式")
        self.countdown_btn.setCheckable(True)
        self.countdown_btn.setObjectName("modeOptionBtn")
        self.mode_group.addButton(self.countdown_btn, 0)
        self.schedule_btn = QPushButton("预约模式")
        self.schedule_btn.setCheckable(True)
        self.schedule_btn.setObjectName("modeOptionBtn")
        self.mode_group.addButton(self.schedule_btn, 1)

        mode_layout.addWidget(self.countdown_btn)
        mode_layout.addWidget(self.schedule_btn)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # 默认选中"预约模式"
        self.schedule_btn.setChecked(True)
        self.mode_group.buttonClicked.connect(self._on_mode_changed)

        # ---- 任务类型（通用设置） ----
        task_layout = QHBoxLayout()
        task_layout.addWidget(QLabel("任务类型："))
        self.task_combo = QComboBox()
        self.task_combo.addItem("关机", "shutdown")
        self.task_combo.addItem("重启", "restart")
        self.task_combo.addItem("注销", "logout")
        self.task_combo.addItem("睡眠", "sleep")
        self.task_combo.addItem("休眠", "hibernate")
        task_layout.addWidget(self.task_combo)
        task_layout.addStretch()
        layout.addLayout(task_layout)

        # ---- 倒计时输入（默认显示） ----
        cd_layout = QHBoxLayout()
        self.countdown_label = QLabel("分钟后关机：")
        cd_layout.addWidget(self.countdown_label)
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(1, 9999)
        self.minutes_spin.setValue(30)
        self.minutes_spin.setSuffix(" 分钟")
        cd_layout.addWidget(self.minutes_spin)
        cd_layout.addStretch()
        layout.addLayout(cd_layout)

        # ---- 定点定时输入（默认隐藏） ----
        # 使用容器 QWidget 统一显示/隐藏整行
        self.schedule_container = QWidget()
        sc_layout = QHBoxLayout(self.schedule_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)

        self.plan_label = QLabel()
        sc_layout.addWidget(self.plan_label)

        plan_btn = QPushButton("设置...")
        plan_btn.clicked.connect(self._open_plan_dialog)
        plan_btn.setFixedWidth(60)
        sc_layout.addWidget(plan_btn)

        sc_layout.addStretch()
        layout.addWidget(self.schedule_container)

        # 初始状态（默认"预约关机"，显示计划选择控件）
        self._on_mode_changed()
        self._update_plan_label()

        # ---- 确定 / 取消 按钮 ----
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("确认")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ======================== 内部方法 ========================

    def _on_mode_changed(self, btn=None):
        """切换模式时显示/隐藏对应的输入控件，同时更新按钮样式"""
        is_countdown = self.countdown_btn.isChecked()
        self.countdown_label.setVisible(is_countdown)
        self.minutes_spin.setVisible(is_countdown)
        self.schedule_container.setVisible(not is_countdown)
        self._update_mode_button_styles()

    def _open_plan_dialog(self):
        """打开计划设置弹窗"""
        dialog = SchedulePlanDialog(self._plan, self)
        if dialog.exec() == QDialog.Accepted:
            self._plan = dialog.get_plan()
            self._update_plan_label()

    def _update_plan_label(self):
        """更新计划摘要文字"""
        pt = self._plan["type"]
        label = PLAN_TYPE_LABELS.get(pt, "未知")
        if pt == "weekly":
            enabled_days = [WEEKDAY_NAMES[i] for i in range(7)
                            if self._plan["weekly_enabled"][i]]
            detail = "、".join(enabled_days) if enabled_days else "未设置"
            self.plan_label.setText(f"计划类型：{label}  ({detail})")
        else:
            self.plan_label.setText(
                f"计划类型：{label}  {self._plan['time'].toString('HH:mm')}"
            )

    def _update_mode_button_styles(self):
        """更新模式按钮的选中/未选中样式"""
        for btn in (self.countdown_btn, self.schedule_btn):
            if btn.isChecked():
                btn.setStyleSheet("""
                    QPushButton#modeOptionBtn {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #4DABF7, stop:1 #339AF0);
                        border: none;
                        border-radius: 8px;
                        padding: 8px 14px;
                        color: #FFFFFF;
                        font-size: 13px;
                        font-weight: bold;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton#modeOptionBtn {
                        background: #FFFFFF;
                        border: 1px solid #DDE3E9;
                        border-radius: 8px;
                        padding: 8px 14px;
                        color: #495057;
                        font-size: 13px;
                    }
                    QPushButton#modeOptionBtn:hover {
                        border-color: #339AF0;
                        color: #339AF0;
                    }
                """)

    # ======================== 外部接口（供主窗口调用） ========================

    def get_mode(self) -> str:
        """返回当前选择的模式名称"""
        if self.countdown_btn.isChecked():
            return "倒计时模式"
        return "预约模式"

    def set_mode(self, mode: str):
        """设置当前模式（兼容旧版配置中"预约关机"）"""
        if mode == "倒计时模式":
            self.countdown_btn.setChecked(True)
        else:
            self.schedule_btn.setChecked(True)
        self._on_mode_changed()

    def set_task_type(self, task_type: str):
        """设置任务类型"""
        for i in range(self.task_combo.count()):
            if self.task_combo.itemData(i) == task_type:
                self.task_combo.setCurrentIndex(i)
                break

    def get_task_type(self) -> str:
        """获取任务类型"""
        return self.task_combo.currentData()

    def get_minutes(self) -> int:
        return self.minutes_spin.value()

    def set_minutes(self, minutes: int):
        self.minutes_spin.setValue(minutes)

    def get_plan(self) -> dict:
        """获取当前计划配置"""
        return self._plan

    def set_plan(self, plan: dict):
        """设置计划配置"""
        self._plan = plan.copy() if plan else SchedulePlanDialog.default_plan()
        self._update_plan_label()
