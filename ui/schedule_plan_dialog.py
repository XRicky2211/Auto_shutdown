# --------------------------------------------------------------------------
# 文件：ui/schedule_plan_dialog.py
# 用途：定时计划设置弹窗——支持 仅一次 / 每天 / 工作日 / 周末 / 每周定时
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QCheckBox, QTimeEdit, QDialogButtonBox, QGroupBox,
    QScrollArea, QWidget,
)
from PySide6.QtCore import QTime

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

PLAN_TYPES = [
    ("once", "仅一次"),
    ("daily", "每天定时"),
    ("weekdays", "工作日计划"),
    ("weekends", "周末计划"),
    ("weekly", "每周定时计划"),
]


class SchedulePlanDialog(QDialog):
    """定时计划设置弹窗"""

    def __init__(self, plan: dict, parent=None):
        """
        参数：
            plan: 当前计划配置，格式见 default_plan()
        """
        super().__init__(parent)
        self.setWindowTitle("定时计划设置")
        self.setFixedSize(420, 380)

        self._plan = plan.copy() if plan else self.default_plan()
        self._setup_ui()
        self._load_plan()

    @staticmethod
    def default_plan() -> dict:
        """返回默认计划配置"""
        return {
            "type": "once",
            "time": QTime(22, 0),
            "weekly_enabled": [False] * 7,
            "weekly_times": [QTime(22, 0) for _ in range(7)],
        }

    # ======================== 界面创建 ========================

    def _setup_ui(self):
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- 计划类型下拉框 ----
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("计划类型："))
        self.type_combo = QComboBox()
        for key, label in PLAN_TYPES:
            self.type_combo.addItem(label, key)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # ---- 单次时间设置（仅一次 / 每天 / 工作日 / 周末） ----
        self.simple_time_group = QGroupBox("时间设置")
        st_layout = QHBoxLayout(self.simple_time_group)
        st_layout.addWidget(QLabel("执行时间："))
        self.simple_time_edit = QTimeEdit()
        self.simple_time_edit.setDisplayFormat("HH:mm")
        self.simple_time_edit.setTime(QTime(22, 0))
        st_layout.addWidget(self.simple_time_edit)
        st_layout.addStretch()
        layout.addWidget(self.simple_time_group)

        # ---- 每周定时设置（7 行） ----
        self.weekly_group = QGroupBox("每周定时设置")
        wg_layout = QVBoxLayout(self.weekly_group)
        wg_layout.setSpacing(6)

        self.weekly_rows = []
        for i, name in enumerate(WEEKDAY_NAMES):
            row = QHBoxLayout()
            row.setSpacing(8)

            cb = QCheckBox(name)
            row.addWidget(cb)

            te = QTimeEdit()
            te.setDisplayFormat("HH:mm")
            te.setTime(QTime(22, 0))
            te.setEnabled(False)
            row.addWidget(te)

            row.addStretch()
            wg_layout.addLayout(row)

            # 启用复选框联动时间控件
            cb.toggled.connect(te.setEnabled)
            self.weekly_rows.append((cb, te))

        layout.addWidget(self.weekly_group)

        # ---- 确定 / 取消 ----
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ======================== 内部方法 ========================

    def _on_type_changed(self, index: int):
        """切换计划类型时显示/隐藏对应的设置区域"""
        plan_type = self.type_combo.currentData()
        is_weekly = plan_type == "weekly"
        self.simple_time_group.setVisible(not is_weekly)
        self.weekly_group.setVisible(is_weekly)
        # 调整窗口高度以适应每周模式
        self.setFixedSize(420, 460 if is_weekly else 380)

    def _load_plan(self):
        """将当前计划数据显示到界面"""
        type_key = self._plan["type"]
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == type_key:
                self.type_combo.setCurrentIndex(i)
                break

        self.simple_time_edit.setTime(self._plan["time"])

        for i, (cb, te) in enumerate(self.weekly_rows):
            cb.setChecked(self._plan["weekly_enabled"][i])
            te.setTime(self._plan["weekly_times"][i])

    # ======================== 外部接口 ========================

    def get_plan(self) -> dict:
        """获取当前设置的计划配置"""
        self._plan["type"] = self.type_combo.currentData()
        self._plan["time"] = self.simple_time_edit.time()

        for i, (cb, te) in enumerate(self.weekly_rows):
            self._plan["weekly_enabled"][i] = cb.isChecked()
            self._plan["weekly_times"][i] = te.time()

        return self._plan
