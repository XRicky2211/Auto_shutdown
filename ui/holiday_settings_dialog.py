# --------------------------------------------------------------------------
# 文件：ui/holiday_settings_dialog.py
# 用途：节假日跳过设置弹窗——开关 + 上个/下个节假日详情（含名称与起止日期）
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QCheckBox,
    QDialogButtonBox, QFrame,
)
from PySide6.QtCore import QDate


class HolidaySettingsDialog(QDialog):
    """节假日跳过设置弹窗"""

    def __init__(self, enabled: bool, holidays: set, periods: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("节假日跳过设置")
        self.setFixedSize(380, 260)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- 启用开关 ----
        self.enabled_cb = QCheckBox("启用节假日自动跳过")
        self.enabled_cb.setChecked(enabled)
        layout.addWidget(self.enabled_cb)

        # ---- 分隔线 ----
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # ---- 节假日信息 ----
        info_text = self._build_info_text(holidays, periods)
        self.info_label = QLabel(info_text)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

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

    def is_enabled(self) -> bool:
        """获取用户是否启用节假日跳过"""
        return self.enabled_cb.isChecked()

    # ======================== 静态辅助方法 ========================

    @staticmethod
    def _format_date(date_str: str) -> str:
        """将 '2026-01-01' 转为 '2026年01月01日'"""
        d = QDate.fromString(date_str, "yyyy-MM-dd")
        return d.toString("yyyy年MM月dd日") if d.isValid() else date_str

    @staticmethod
    def _format_period(period: dict) -> str:
        """格式化节假日区间字符串"""
        name = period["name"]
        start = HolidaySettingsDialog._format_date(period["start"])
        end = HolidaySettingsDialog._format_date(period["end"])
        if period["start"] == period["end"]:
            return f"{name}：{start}"
        return f"{name}：{start}—{end}"

    @staticmethod
    def _build_info_text(holidays: set, periods: list) -> str:
        """生成节假日统计信息文本"""
        today = QDate.currentDate()
        today_str = today.toString("yyyy-MM-dd")

        lines = []
        lines.append(f"当年共 {len(holidays)} 个法定节假日")

        if today_str in holidays:
            lines.append("今日是法定节假日")

        # 查找过去和未来的节假日区间
        past = [p for p in periods if p["end"] < today_str]
        future = [p for p in periods if p["start"] >= today_str]

        if past:
            lines.append("上个节假日：" + HolidaySettingsDialog._format_period(past[-1]))
        if future:
            lines.append("下个节假日：" + HolidaySettingsDialog._format_period(future[0]))

        return "\n".join(lines) if lines else "暂未获取到节假日数据"
