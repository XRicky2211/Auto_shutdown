# --------------------------------------------------------------------------
# 文件：ui/reminder_dialog.py
# 用途：关机前弹出的提醒窗口，包含 取消/推迟/立即关机 三个按钮
# --------------------------------------------------------------------------

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtCore import Signal, Qt, QTimer, QDateTime


class ReminderDialog(QDialog):
    """关机前提醒弹窗"""

    # 自定义信号：当用户点击按钮时发射
    cancelled = Signal()       # 取消关机
    delayed = Signal(int)      # 推迟关机，参数是推迟的分钟数
    confirmed = Signal()       # 确认预约（倒计时继续，到点自动执行）

    def __init__(self, minutes_before: int, delay_minutes: int, action_name: str = "关机",
                 end_time=None, remaining_seconds: int = 0, parent=None,
                 title_text=None):
        """
        参数：
            minutes_before: 距离关机的分钟数（显示用）
            delay_minutes:  推迟按钮的默认分钟数
            action_name:    任务类型名称（关机/重启/注销/睡眠/休眠）
            end_time:       任务执行的具体时间 (QDateTime)
            remaining_seconds: 剩余秒数
            title_text:     自定义标题文字（设置后替换顶部的执行时间文字）
        """
        super().__init__(parent)
        self._action_name = action_name
        self._remaining_seconds = remaining_seconds
        self._end_time = end_time
        self._title_text = title_text
        self.setWindowTitle(f"{action_name}提醒")
        self.setFixedSize(360, 180)

        # 让窗口保持在最前
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._setup_ui(minutes_before, delay_minutes, end_time, remaining_seconds)

        # 启动每秒刷新定时器，让时间实时变化
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self._refresh_display)
        self._refresh_timer.start()

    def _refresh_display(self):
        """每秒刷新剩余时间和执行时间显示（用系统时间消除累积误差）"""
        if self._end_time:
            remaining = QDateTime.currentDateTime().secsTo(self._end_time)
            self._remaining_seconds = remaining if remaining >= 0 else 0
        else:
            self._remaining_seconds -= 1
        if self._remaining_seconds < 0:
            self._refresh_timer.stop()
            return
        remain_str = self._format_remaining(self._remaining_seconds)
        self._remain_label.setText(f"剩余 {remain_str}")
        if self._end_time and not self._title_text:
            self._exec_label.setText(
                f"将于 {self._end_time.toString('HH:mm:ss')} 执行{self._action_name}任务"
            )

    @staticmethod
    def _format_remaining(seconds: int) -> str:
        """将秒数格式化为 HH:MM:SS"""
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _setup_ui(self, minutes_before: int, delay_minutes: int, end_time, remaining_seconds: int):
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ---- 时间信息区域 ----
        time_widget = QWidget()
        time_widget.setStyleSheet("""
            background-color: #F0F7FF;
            border: 1px solid #D0E8FF;
            border-radius: 8px;
            padding: 8px;
        """)
        tl = QVBoxLayout(time_widget)
        tl.setContentsMargins(12, 8, 12, 8)
        tl.setSpacing(4)

        # 标题文字（自定义或默认显示执行时间）
        if self._title_text:
            default_text = self._title_text
        else:
            end_str = end_time.toString("HH:mm:ss") if end_time else "--:--:--"
            default_text = f"将于 {end_str} 执行{self._action_name}任务"
        self._exec_label = QLabel(default_text)
        self._exec_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1C7ED6; border: none;")
        self._exec_label.setAlignment(Qt.AlignCenter)
        tl.addWidget(self._exec_label)

        # 剩余时间
        remain_str = self._format_remaining(remaining_seconds)
        self._remain_label = QLabel(f"剩余 {remain_str}")
        self._remain_label.setStyleSheet("font-size: 13px; color: #495057; border: none;")
        self._remain_label.setAlignment(Qt.AlignCenter)
        tl.addWidget(self._remain_label)

        layout.addWidget(time_widget)

        # ---- 三个按钮 ----
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        cancel_btn = QPushButton(f"取消{self._action_name}")
        delay_btn = QPushButton(f"推迟 {delay_minutes} 分钟")
        shutdown_btn = QPushButton("确认预约")

        # 给按钮加一点样式
        for btn in (cancel_btn, delay_btn, shutdown_btn):
            btn.setMinimumHeight(36)
        shutdown_btn.setStyleSheet("background-color: #339AF0; color: white; font-weight: bold;")

        # 绑定点击事件
        cancel_btn.clicked.connect(self._on_cancelled)
        delay_btn.clicked.connect(lambda: self._on_delayed(delay_minutes))
        shutdown_btn.clicked.connect(self._on_shutdown_now)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(delay_btn)
        btn_layout.addWidget(shutdown_btn)

        layout.addLayout(btn_layout)

    # ---- 按钮响应 ----

    def _on_cancelled(self):
        """用户点击了"取消关机" """
        self.cancelled.emit()
        self.close()

    def _on_delayed(self, minutes: int):
        """用户点击了"推迟" """
        self.delayed.emit(minutes)
        self.close()

    def _on_shutdown_now(self):
        """用户点击了"确认预约" """
        self.confirmed.emit()
        self.close()
