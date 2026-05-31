# --------------------------------------------------------------------------
# 文件：ui/low_battery_dialog.py
# 用途：低电量警告弹窗——自定义样式，支持两级警告（warning / critical）
# --------------------------------------------------------------------------

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QProgressBar,
)
from PySide6.QtCore import Qt, QTimer


class LowBatteryDialog(QDialog):
    """低电量警告弹窗

    两级警告：
    - warning：  普通提醒，蓝色调，用户点击"我知道了"后不再重复打扰
    - critical： 严重警告，红色调，倒计时结束后自动关机

    调用方在 exec() 后检查以下属性获取用户操作：
        shutdown_requested (bool): 用户要求立即关机
        session_disabled   (bool): 用户要求本次禁用
        postponed          (bool): 用户要求推迟（仅 critical）
        postponed_minutes  (int):  推迟分钟数
    """

    def __init__(self, percentage: float, remaining_text: str,
                 level: str = "warning", parent=None):
        """
        参数：
            percentage:     当前电量百分比
            remaining_text: 预估剩余时间文字（可为空字符串）
            level:          "warning" 或 "critical"
        """
        super().__init__(parent)
        self._percentage = percentage
        self._remaining_text = remaining_text
        self._level = level

        # 按钮操作结果
        self.shutdown_requested = False
        self.session_disabled = False
        self.postponed = False
        self.postponed_minutes = 5

        # critical 级别：自动关机倒计时
        self._auto_shutdown_seconds = 60
        self._countdown_timer = None

        self._setup_window()
        self._setup_ui()

        if level == "critical":
            self._start_countdown()

    # ======================== 窗口设置 ========================

    def _setup_window(self):
        """配置窗口属性"""
        if self._level == "warning":
            self.setWindowTitle("低电量提醒")
        else:
            self.setWindowTitle("电池电量严重不足")

        self.setFixedSize(400, 220)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTitleHint
            | Qt.CustomizeWindowHint
        )
        self.setModal(True)

    # ======================== 界面创建 ========================

    def _setup_ui(self):
        """创建弹窗界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ---- 信息区域（带背景色） ----
        info_widget = QWidget()
        if self._level == "warning":
            info_widget.setStyleSheet("""
                background-color: #F0F7FF;
                border: 1px solid #D0E8FF;
                border-radius: 8px;
                padding: 8px;
            """)
        else:
            info_widget.setStyleSheet("""
                background-color: #FFF0F0;
                border: 1px solid #FFD0D0;
                border-radius: 8px;
                padding: 8px;
            """)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(12, 8, 12, 8)
        info_layout.setSpacing(6)

        # 电量文字
        if self._level == "warning":
            color = "#E8590C"
        else:
            color = "#E03131"

        self._pct_label = QLabel(
            f"电池电量：<b style='color:{color};font-size:20px'>{self._percentage:.0f}%</b>"
        )
        self._pct_label.setStyleSheet("border: none; font-size: 14px;")
        info_layout.addWidget(self._pct_label)

        # 预估剩余时间
        trend_color = "#495057" if self._remaining_text else "#868E96"
        self._trend_label = QLabel(
            self._remaining_text or "数据收集中..."
        )
        self._trend_label.setStyleSheet(
            f"border: none; font-size: 13px; color: {trend_color};"
        )
        info_layout.addWidget(self._trend_label)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(int(round(self._percentage)))
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(12)

        # 进度条颜色
        bar_color = self._get_progress_color()
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #DDE3E9;
                border-radius: 6px;
                background-color: #F1F3F5;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 5px;
            }}
        """)
        info_layout.addWidget(self._progress)

        # critical 级别：倒计时文字
        if self._level == "critical":
            self._countdown_label = QLabel(
                f"若不操作，系统将在 {self._auto_shutdown_seconds} 秒后自动关机"
            )
            self._countdown_label.setStyleSheet(
                "border: none; font-size: 12px; color: #E03131; font-weight: bold;"
            )
            self._countdown_label.setAlignment(Qt.AlignCenter)
            info_layout.addWidget(self._countdown_label)

        layout.addWidget(info_widget)

        # ---- 按钮区域 ----
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        if self._level == "warning":
            self._build_warning_buttons(btn_layout)
        else:
            self._build_critical_buttons(btn_layout)

        layout.addLayout(btn_layout)

    def _get_progress_color(self) -> str:
        """根据电量返回进度条颜色"""
        pct = self._percentage
        if pct <= 10:
            return "#E03131"   # 红色
        elif pct <= 20:
            return "#E8590C"   # 深橙
        elif pct <= 30:
            return "#FD7E14"   # 橙色
        elif pct <= 60:
            return "#F59F00"   # 黄色
        else:
            return "#40C057"   # 绿色

    def _style_button(self, btn: QPushButton, bg: str, fg: str = "white"):
        """给按钮设置统一样式"""
        btn.setMinimumHeight(34)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.85;
            }}
        """)

    # ======================== Warning 级别按钮 ========================

    def _build_warning_buttons(self, layout: QHBoxLayout):
        """warning 级别的三个按钮"""
        dismiss_btn = QPushButton("我知道了")
        self._style_button(dismiss_btn, "#868E96")
        dismiss_btn.clicked.connect(self._on_dismissed)
        layout.addWidget(dismiss_btn)

        shutdown_btn = QPushButton("立即关机")
        self._style_button(shutdown_btn, "#E03131")
        shutdown_btn.clicked.connect(self._on_shutdown)
        layout.addWidget(shutdown_btn)

        disable_btn = QPushButton("本次禁用")
        self._style_button(disable_btn, "#F1F3F5", "#495057")
        disable_btn.clicked.connect(self._on_disable)
        layout.addWidget(disable_btn)

    # ======================== Critical 级别按钮 ========================

    def _build_critical_buttons(self, layout: QHBoxLayout):
        """critical 级别的三个按钮"""
        postpone_btn = QPushButton("推迟 5 分钟")
        self._style_button(postpone_btn, "#F59F00")
        postpone_btn.clicked.connect(self._on_postpone)
        layout.addWidget(postpone_btn)

        shutdown_btn = QPushButton("立即关机")
        self._style_button(shutdown_btn, "#E03131")
        shutdown_btn.clicked.connect(self._on_shutdown)
        layout.addWidget(shutdown_btn)

        disable_btn = QPushButton("本次禁用")
        self._style_button(disable_btn, "#F1F3F5", "#495057")
        disable_btn.clicked.connect(self._on_disable)
        layout.addWidget(disable_btn)

    # ======================== Critical 级倒计时 ========================

    def _start_countdown(self):
        """启动自动关机倒计时（每秒更新）"""
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick_countdown)
        self._countdown_timer.start()

    def _tick_countdown(self):
        """每秒减少倒计时，到 0 自动关机"""
        self._auto_shutdown_seconds -= 1
        if self._auto_shutdown_seconds <= 0:
            self._countdown_timer.stop()
            self.shutdown_requested = True
            self.accept()
            return

        self._countdown_label.setText(
            f"若不操作，系统将在 {self._auto_shutdown_seconds} 秒后自动关机"
        )

    # ======================== 按钮事件 ========================

    def _on_dismissed(self):
        """用户点击"我知道了" """
        self.shutdown_requested = False
        self.session_disabled = False
        self.postponed = False
        self.accept()

    def _on_shutdown(self):
        """用户点击"立即关机" """
        if self._countdown_timer:
            self._countdown_timer.stop()
        self.shutdown_requested = True
        self.accept()

    def _on_disable(self):
        """用户点击"本次禁用" """
        if self._countdown_timer:
            self._countdown_timer.stop()
        self.session_disabled = True
        self.accept()

    def _on_postpone(self):
        """用户点击"推迟 5 分钟" """
        if self._countdown_timer:
            self._countdown_timer.stop()
        self.postponed = True
        self.accept()
