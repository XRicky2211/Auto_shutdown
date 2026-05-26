# --------------------------------------------------------------------------
# 文件：ui/main_window.py
# 用途：程序主窗口——简洁卡片式界面，蓝白银配色
# --------------------------------------------------------------------------

import os
import sys
import subprocess
import threading
import winreg

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QFrame, QDialog,
    QGraphicsDropShadowEffect, QSystemTrayIcon, QMenu, QApplication,
)
from PySide6.QtCore import Qt, QTimer, QTime, QDateTime, QDate, QRect, QSettings
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPen

from ui.timer_settings_dialog import TimerSettingsDialog
from ui.reminder_settings_dialog import ReminderSettingsDialog
from ui.reminder_dialog import ReminderDialog
from core.battery_monitor import BatteryMonitor
from ui.battery_settings_dialog import BatterySettingsDialog
from ui.schedule_plan_dialog import SchedulePlanDialog
from ui.holiday_settings_dialog import HolidaySettingsDialog
from core.config_manager import load_settings, save_settings
from core.holiday_api import fetch_holiday_data
from core.game_detector import is_fullscreen_app_running
from ui.game_mode_settings_dialog import GameModeSettingsDialog

# ---- 任务类型常量 ----
TASK_TYPES = {
    "shutdown": "关机",
    "restart": "重启",
    "logout": "注销",
    "sleep": "睡眠",
    "hibernate": "休眠",
}

TASK_COMMANDS = {
    "shutdown": ["shutdown", "/s", "/t", "0"],
    "restart": ["shutdown", "/r", "/t", "0"],
    "logout": ["shutdown", "/l"],
    "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,0,0"],
    "hibernate": ["shutdown", "/h"],
}


class MainWindow(QMainWindow):
    """自动关机助手的主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("自动关机助手")
        self.setMinimumSize(420, 360)

        # ---- 定时设置（默认值） ----
        self.current_mode = "预约模式"
        self.countdown_minutes = 30
        self.target_time = QTime.currentTime().addSecs(3600)
        self.schedule_plan = SchedulePlanDialog.default_plan()
        self.task_type = "shutdown"

        # ---- 提醒设置（默认值） ----
        self.reminder_times = [1, 30]
        self.delay_minutes = 10

        # ---- 倒计时状态 ----
        self.remaining_seconds = 0
        self.is_counting = False
        self.end_time = QDateTime()
        self.fired_reminders = set()
        self.reminder_dialog = None
        self.is_shutting_down = False

        # ---- 低电量自动关机 ----
        self.low_battery_enabled = True
        self.low_battery_threshold = 15
        self.low_battery_warned = False
        self.low_battery_disabled = False
        self.holidays: set = set()
        self.holiday_periods: list = []
        self.holiday_skip_enabled = False
        self.auto_start_enabled = False

        # ---- 每周定时自动恢复 ----
        self.schedule_active = False

        # ---- 游戏模式状态 ----
        self.game_mode_enabled = False
        self.game_end_countdown = 60   # 游戏结束后倒计时秒数（可配置）
        self.game_postponing = False
        self.game_end_warning_shown = False
        self.game_end_msg = None

        self._load_config()
        self._init_holidays()
        self.auto_start_enabled = self._check_auto_start()
        self._setup_ui()
        self._update_game_mode_button()
        self.setWindowIcon(self._make_shutdown_pixmap(64))
        self._restore_window_geometry()
        self._setup_timer()
        self._setup_battery_monitor()
        self._update_summary()
        self._setup_tray()

        # 开机后自动恢复每周定时任务
        if self.schedule_active:
            QTimer.singleShot(500, self._auto_resume_countdown)

    # ======================== 界面创建 ========================

    def _setup_ui(self):
        """创建主窗口界面——卡片式布局"""
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 24, 20, 20)
        layout.setSpacing(16)

        # ---- 标题 ----
        title = QLabel("自动关机 · 重启 · 注销 · 睡眠 · 休眠")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #339AF0;
            padding-bottom: 4px;
        """)
        layout.addWidget(title)

        # ---- 顶部两个设置按钮（等宽、蓝底白字） ----
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        timer_btn = QPushButton("定时设置")
        timer_btn.setObjectName("settingBtn")
        timer_btn.clicked.connect(self._open_timer_settings)

        reminder_btn = QPushButton("提醒设置")
        reminder_btn.setObjectName("settingBtn")
        reminder_btn.clicked.connect(self._open_reminder_settings)

        btn_layout.addWidget(timer_btn)
        btn_layout.addWidget(reminder_btn)
        layout.addLayout(btn_layout)

        # ---- 状态卡片 ----
        card = QFrame()
        card.setObjectName("statusCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(10)

        self.shutdown_time_label = QLabel(self._get_expected_time_label())
        card_layout.addWidget(self.shutdown_time_label)

        self.remaining_label = QLabel("剩余时间：--")
        card_layout.addWidget(self.remaining_label)

        self.battery_label = QLabel("当前电量：--")
        card_layout.addWidget(self.battery_label)

        self.holiday_label = QLabel("今日节假日，自动跳过关机")
        self.holiday_label.setStyleSheet("color: #E74C3C; font-weight: bold;")
        self.holiday_label.setAlignment(Qt.AlignCenter)
        self.holiday_label.setVisible(False)
        card_layout.addWidget(self.holiday_label)

        # 卡片阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)

        layout.addWidget(card)

        # ---- 弹性空间，让按钮沉底 ----
        layout.addStretch()

        # ---- 启动 / 取消按钮 ----
        self.action_btn = QPushButton(self._get_start_btn_text())
        self.action_btn.setObjectName("actionBtn")
        self.action_btn.clicked.connect(self._toggle_countdown)
        layout.addWidget(self.action_btn)

        # ---- 底部小按钮行（开机自启 / 节假日跳过 / 低电量等设置） ----
        bottom_btn_layout = QHBoxLayout()
        bottom_btn_layout.setSpacing(8)

        self.auto_start_btn = QPushButton("开机自启")
        self.auto_start_btn.setObjectName("bottomSettingBtn")
        self.auto_start_btn.clicked.connect(self._toggle_auto_start)
        bottom_btn_layout.addWidget(self.auto_start_btn)

        self.holiday_btn = QPushButton("节假日跳过")
        self.holiday_btn.setObjectName("bottomSettingBtn")
        self.holiday_btn.clicked.connect(self._open_holiday_settings)
        bottom_btn_layout.addWidget(self.holiday_btn)

        self.game_mode_btn = QPushButton("游戏模式")
        self.game_mode_btn.setObjectName("bottomSettingBtn")
        self.game_mode_btn.clicked.connect(self._open_game_settings)
        bottom_btn_layout.addWidget(self.game_mode_btn)

        bottom_btn_layout.addStretch()
        self.low_battery_btn = QPushButton("低电量设置")
        self.low_battery_btn.setObjectName("bottomSettingBtn")
        self.low_battery_btn.clicked.connect(self._open_battery_settings)
        bottom_btn_layout.addWidget(self.low_battery_btn)
        layout.addLayout(bottom_btn_layout)

        # ---- 底部设置摘要（小字） ----
        self.summary_label = QLabel()
        self.summary_label.setObjectName("summaryLabel")
        self.summary_label.setAlignment(Qt.AlignCenter)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # ---- 全局样式表 ----
        self._apply_stylesheet()
        self._update_auto_start_button()

    def _apply_stylesheet(self):
        """应用全局样式——蓝白银配色、圆角、阴影"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F8F9FA;
            }
            QWidget#centralWidget {
                background-color: #F8F9FA;
            }
            QPushButton#settingBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4DABF7, stop:1 #339AF0);
                border: none;
                border-radius: 10px;
                padding: 10px 0;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                min-height: 44px;
            }
            QPushButton#settingBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #339AF0, stop:1 #228BE6);
            }
            QPushButton#settingBtn:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #228BE6, stop:1 #1C7ED6);
            }
            QFrame#statusCard {
                background-color: #FFFFFF;
                border: 1px solid #DDE3E9;
                border-radius: 12px;
            }
            QFrame#statusCard QLabel {
                color: #343A40;
                font-size: 14px;
                padding: 4px 0;
            }
            QPushButton#actionBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4DABF7, stop:1 #339AF0);
                border: none;
                border-radius: 10px;
                padding: 12px 0;
                color: #FFFFFF;
                font-size: 15px;
                font-weight: bold;
                min-height: 44px;
            }
            QPushButton#actionBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #339AF0, stop:1 #228BE6);
            }
            QPushButton#actionBtn:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #228BE6, stop:1 #1C7ED6);
            }
            QLabel#summaryLabel {
                color: #868E96;
                font-size: 12px;
                padding: 0;
            }
            QPushButton#bottomSettingBtn {
                background: transparent;
                border: 1px solid #DDE3E9;
                border-radius: 6px;
                padding: 4px 10px;
                color: #868E96;
                font-size: 11px;
                min-height: 24px;
            }
            QPushButton#bottomSettingBtn:hover {
                border-color: #339AF0;
                color: #339AF0;
            }
        """)

    # ======================== 窗口大小记忆 ========================

    def _restore_window_geometry(self):
        """恢复上次关闭时的窗口大小和位置"""
        settings = QSettings("AutoShutdown", "AutoShutdownHelper")
        geometry = settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(420, 400)  # 默认大小，保证文字完整显示

    def closeEvent(self, event):
        """关闭按钮隐藏到系统托盘（不退出程序）"""
        settings = QSettings("AutoShutdown", "AutoShutdownHelper")
        settings.setValue("window/geometry", self.saveGeometry())
        self._save_all_settings()
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            super().closeEvent(event)

    # ======================== 倒计时器 ========================

    def _setup_timer(self):
        """创建每秒触发一次的倒计时器"""
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._on_tick)

    # ======================== 设置摘要（底部小字） ========================

    @property
    def _task_action_name(self) -> str:
        """获取当前任务类型的中文名称"""
        return TASK_TYPES.get(self.task_type, "关机")

    def _get_start_btn_text(self) -> str:
        """获取启动按钮文字"""
        return f"启动定时{self._task_action_name}"

    def _get_cancel_btn_text(self) -> str:
        """获取取消按钮文字"""
        return f"取消定时{self._task_action_name}"

    def _get_expected_time_label(self, time_str="--") -> str:
        """获取预计执行时间标签文字"""
        return f"预计{self._task_action_name}时间：{time_str}"

    def _get_plan_summary(self) -> str:
        """生成当前计划的文字描述"""
        action = self._task_action_name
        pt = self.schedule_plan["type"]
        if self.current_mode == "倒计时模式":
            return f"倒计时 {self.countdown_minutes} 分钟后{action}"
        labels = {"once": "仅一次", "daily": "每天", "weekdays": "工作日",
                  "weekends": "周末", "weekly": "每周定时"}
        label = labels.get(pt, "预约")
        if pt == "weekly":
            names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            days = [names[i] for i in range(7) if self.schedule_plan["weekly_enabled"][i]]
            return f"{label}（{'、'.join(days) or '未设置'}）后{action}"
        return f"{label} {self.schedule_plan['time'].toString('HH:mm')} 后{action}"

    def _update_summary(self):
        """更新底部的定时设置摘要"""
        time_text = self._get_plan_summary()

        # 节假日提示（仅预约模式）
        holiday_text = ""
        if self.current_mode == "预约模式" and self._is_holiday_date(QDate.currentDate()):
            holiday_text = "  ｜  节假日跳过"

        # 游戏模式提示
        game_text = ""
        if self.game_mode_enabled:
            game_text = f"  ｜  游戏模式({self.game_end_countdown}s)"

        reminder_text = "、".join(f"{t}分钟前" for t in self.reminder_times)
        self.summary_label.setText(
            f"{time_text}  ｜  提醒：{reminder_text}  ｜  推迟：{self.delay_minutes}分钟{holiday_text}{game_text}"
        )

    # ======================== 打开设置弹窗 ========================

    def _open_timer_settings(self):
        """打开定时设置弹窗"""
        dialog = TimerSettingsDialog(self.schedule_plan, self)
        dialog.set_mode(self.current_mode)
        dialog.set_minutes(self.countdown_minutes)
        dialog.set_task_type(self.task_type)
        if dialog.exec() == QDialog.Accepted:
            self.current_mode = dialog.get_mode()
            self.countdown_minutes = dialog.get_minutes()
            self.schedule_plan = dialog.get_plan()
            self.task_type = dialog.get_task_type()
            self.target_time = self.schedule_plan["time"]
            self.action_btn.setText(self._get_start_btn_text())
            self.shutdown_time_label.setText(self._get_expected_time_label())
            self.schedule_active = False
            self._update_summary()
            self._save_all_settings()

    def _open_reminder_settings(self):
        """打开提醒设置弹窗"""
        dialog = ReminderSettingsDialog(self.reminder_times, self.delay_minutes, self)
        if dialog.exec() == QDialog.Accepted:
            self.reminder_times = dialog.get_reminder_times()
            self.delay_minutes = dialog.get_delay_minutes()
            self._update_summary()
            self._save_all_settings()

    def _open_holiday_settings(self):
        """打开节假日跳过设置弹窗"""
        dialog = HolidaySettingsDialog(
            self.holiday_skip_enabled, self.holidays, self.holiday_periods, self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.holiday_skip_enabled = dialog.is_enabled()
            self._update_summary()
            # 如果倒计时运行中，刷新节假日标签显示
            if self.is_counting:
                if (self.current_mode == "预约模式"
                        and self.holiday_skip_enabled
                        and self._is_holiday_date(QDate.currentDate())):
                    self.holiday_label.show()
                else:
                    self.holiday_label.hide()
            self._save_all_settings()

    def _update_auto_start_button(self):
        """更新开机自启按钮的样式"""
        if self.auto_start_enabled:
            self.auto_start_btn.setText("开机自启 ✓")
            self.auto_start_btn.setStyleSheet("""
                QPushButton#bottomSettingBtn {
                    background: transparent;
                    border: 1px solid #339AF0;
                    border-radius: 6px;
                    padding: 4px 10px;
                    color: #339AF0;
                    font-size: 11px;
                    min-height: 24px;
                }
            """)
        else:
            self.auto_start_btn.setText("开机自启")
            self.auto_start_btn.setStyleSheet("")  # 恢复全局样式

    # ======================== 游戏模式 ========================

    def _open_game_settings(self):
        """打开游戏模式设置弹窗"""
        dialog = GameModeSettingsDialog(self.game_mode_enabled, self.game_end_countdown, self)
        if dialog.exec() == QDialog.Accepted:
            self.game_mode_enabled = dialog.is_enabled()
            self.game_end_countdown = dialog.get_countdown_seconds()
            if not self.game_mode_enabled:
                self.game_postponing = False
                self.game_end_warning_shown = False
            self._update_game_mode_button()
            self._update_summary()
            self._save_all_settings()

    def _update_game_mode_button(self):
        """更新游戏模式按钮样式"""
        if self.game_mode_enabled:
            self.game_mode_btn.setText(f"游戏模式({self.game_end_countdown}s) ✓")
            self.game_mode_btn.setStyleSheet("""
                QPushButton#bottomSettingBtn {
                    background: transparent;
                    border: 1px solid #339AF0;
                    border-radius: 6px;
                    padding: 4px 10px;
                    color: #339AF0;
                    font-size: 11px;
                    min-height: 24px;
                }
            """)
        else:
            self.game_mode_btn.setText("游戏模式")
            self.game_mode_btn.setStyleSheet("")

    # ======================== 节假日自动跳过 ========================

    def _init_holidays(self):
        """后台获取节假日数据，避免阻塞 UI 启动"""
        cfg = load_settings()
        cache = cfg.get("holiday_cache", {})
        if isinstance(cache, dict):
            self.holidays = set(cache.get("dates", []))
            self.holiday_periods = cache.get("periods", [])

        def _background_fetch():
            year = QDate.currentDate().year()
            h, p = fetch_holiday_data(year)
            self.holidays = h
            self.holiday_periods = p

        threading.Thread(target=_background_fetch, daemon=True).start()

    def _is_holiday_date(self, d: QDate) -> bool:
        """判断指定日期是否为法定节假日（受开关控制）"""
        if not self.holiday_skip_enabled:
            return False
        return d.toString("yyyy-MM-dd") in self.holidays

    # ======================== 开机自启 ========================

    _REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _REG_VALUE_NAME = "AutoShutdownHelper"

    @staticmethod
    def _get_startup_command() -> str:
        """获取开机自启的完整命令行"""
        if getattr(sys, "frozen", False):
            return sys.executable
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        script = os.path.abspath(sys.argv[0])
        return f'"{pythonw}" "{script}"'

    def _check_auto_start(self) -> bool:
        """检测当前是否已启用开机自启（通过注册表 Run 键）"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._REG_PATH, 0, winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, self._REG_VALUE_NAME)
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except OSError:
            return False

    def _toggle_auto_start(self):
        """切换开机自启状态（通过注册表 Run 键）"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._REG_PATH, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ,
            )
        except OSError:
            QMessageBox.warning(self, "错误", "无法访问系统注册表，请以管理员身份运行。")
            return

        try:
            if self.auto_start_enabled:
                try:
                    winreg.DeleteValue(key, self._REG_VALUE_NAME)
                except FileNotFoundError:
                    pass
                self.auto_start_enabled = False
            else:
                cmd = self._get_startup_command()
                winreg.SetValueEx(key, self._REG_VALUE_NAME, 0, winreg.REG_SZ, cmd)
                self.auto_start_enabled = True
        except OSError as e:
            QMessageBox.warning(self, "错误", f"修改开机自启失败：{e}")
        finally:
            winreg.CloseKey(key)
        self._update_auto_start_button()

    # ======================== 倒计时控制 ========================

    def _toggle_countdown(self):
        """启动 / 取消 倒计时"""
        if not self.is_counting:
            self._start_countdown()
        else:
            self._cancel_countdown()

    def _get_next_schedule_time(self) -> QDateTime:
        """根据当前计划计算下一次任务执行时间（跳过法定节假日）"""
        now = QDateTime.currentDateTime()
        plan = self.schedule_plan

        if plan["type"] in ("once", "daily"):
            target = QDateTime(now.date(), plan["time"])
            if target <= now:
                target = target.addDays(1)
            while self._is_holiday_date(target.date()):
                target = target.addDays(1)
            return target

        if plan["type"] in ("weekdays", "weekends"):
            target = QDateTime(now.date(), plan["time"])
            for _ in range(14):
                dow = target.date().dayOfWeek()
                is_weekday_match = (plan["type"] == "weekdays" and 1 <= dow <= 5)
                is_weekend_match = (plan["type"] == "weekends" and dow in (6, 7))
                if (target > now and (is_weekday_match or is_weekend_match)
                        and not self._is_holiday_date(target.date())):
                    return target
                target = target.addDays(1)
            return target

        if plan["type"] == "weekly":
            current_dow = now.date().dayOfWeek()
            for offset in range(14):
                idx = (current_dow - 1 + offset) % 7
                if plan["weekly_enabled"][idx]:
                    target = QDateTime(now.date().addDays(offset), plan["weekly_times"][idx])
                    if target > now and not self._is_holiday_date(target.date()):
                        return target
            return target

        # fallback
        target = QDateTime(now.date(), plan["time"])
        if target <= now:
            target = target.addDays(1)
        while self._is_holiday_date(target.date()):
            target = target.addDays(1)
        return target

    def _start_countdown(self):
        """开始倒计时（按钮变红+文字切换）"""
        if self.current_mode == "倒计时模式":
            total_seconds = self.countdown_minutes * 60
        else:
            next_time = self._get_next_schedule_time()
            now = QDateTime.currentDateTime()
            if next_time <= now:
                QMessageBox.warning(self, "时间错误", "目标时间已过，请重新设置！")
                return
            total_seconds = now.secsTo(next_time)
            self.target_time = next_time.time()

        if total_seconds <= 0:
            QMessageBox.warning(self, "错误", "请设置一个未来的时间！")
            return

        self.remaining_seconds = total_seconds
        self.end_time = QDateTime.currentDateTime().addSecs(total_seconds)
        self.fired_reminders.clear()
        self.is_shutting_down = False

        if self.current_mode == "预约模式" and self._is_holiday_date(QDate.currentDate()):
            self.holiday_label.show()
        else:
            self.holiday_label.hide()

        self.is_counting = True
        self.action_btn.setText(self._get_cancel_btn_text())

        # 每周定时计划启动后标记为"活跃"，便于开机自动恢复
        if self.current_mode == "预约模式" and self.schedule_plan["type"] == "weekly":
            self.schedule_active = True
            self._save_all_settings()
        self.action_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FF6B6B, stop:1 #E74C3C);
                border: none;
                border-radius: 10px;
                padding: 12px 0;
                color: #FFFFFF;
                font-size: 15px;
                font-weight: bold;
                min-height: 44px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #E74C3C, stop:1 #C0392B);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #C0392B, stop:1 #A93226);
            }
        """)
        self._update_display()

        self.timer.start()
        self._update_tray_menu()

    def _auto_resume_countdown(self):
        """开机后自动恢复每周定时预约任务"""
        if self.is_counting:
            return
        if self.current_mode != "预约模式" or self.schedule_plan["type"] != "weekly":
            self.schedule_active = False
            self._save_all_settings()
            return
        self._start_countdown()

    def _cancel_countdown(self):
        """取消倒计时，重置状态（按钮恢复蓝色）"""
        # 重置游戏模式状态
        self.game_postponing = False
        self.game_end_warning_shown = False
        if self.game_end_msg:
            self.game_end_msg.close()
            self.game_end_msg = None

        self.timer.stop()
        self.is_counting = False
        self.action_btn.setText(self._get_start_btn_text())
        self.action_btn.setStyleSheet("")  # 恢复全局蓝色渐变样式
        self.remaining_label.setText("剩余时间：--")
        self.shutdown_time_label.setText(self._get_expected_time_label())
        self.fired_reminders.clear()
        if self.reminder_dialog and self.reminder_dialog.isVisible():
            self.reminder_dialog.close()
            self.reminder_dialog = None
        self.holiday_label.hide()
        self.schedule_active = False
        self._save_all_settings()
        self._update_tray_menu()

    # ======================== 倒计时核心逻辑 ========================

    def _on_tick(self):
        """每秒执行一次（由 QTimer 触发）"""
        if not self.is_counting:
            return

        # 用 end_time 重新计算剩余时间，消除 timer 不准带来的累积误差
        remaining = QDateTime.currentDateTime().secsTo(self.end_time)
        self.remaining_seconds = remaining if remaining >= 0 else 0

        if self.remaining_seconds <= 0:
            # ① 游戏模式：警告已显示过 → 执行任务（无论游戏是否再运行）
            if self.game_mode_enabled and self.game_end_warning_shown:
                self.timer.stop()
                self._execute_task()
                return

            # ② 游戏模式：全屏程序运行中 → 推迟 15 分钟
            if self.game_mode_enabled and is_fullscreen_app_running():
                self.remaining_seconds = 15 * 60
                self.game_postponing = True
                self.end_time = QDateTime.currentDateTime().addSecs(15 * 60)
                self._update_display()
                return

            # ③ 游戏模式：游戏刚结束（之前推迟过）→ 显示警告，倒计时后执行
            if self.game_mode_enabled and self.game_postponing:
                self.game_postponing = False
                self.game_end_warning_shown = True
                self.remaining_seconds = self.game_end_countdown
                self.end_time = QDateTime.currentDateTime().addSecs(self.game_end_countdown)
                self._show_game_end_warning()
                self._update_display()
                return

            # ④ 正常执行任务
            self.timer.stop()
            self._execute_task()
            return

        # 推迟期间跳过提醒弹窗
        if not self.game_postponing:
            for reminder_min in self.reminder_times:
                reminder_sec = reminder_min * 60
                if self.remaining_seconds <= reminder_sec and reminder_min not in self.fired_reminders:
                    self._show_reminder(reminder_min)
                    self.fired_reminders.add(reminder_min)

        self._update_display()

    def _update_display(self):
        """更新剩余时间和预计关机时间的显示（同时刷新托盘菜单）"""
        hours = self.remaining_seconds // 3600
        minutes = (self.remaining_seconds % 3600) // 60
        secs = self.remaining_seconds % 60
        time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"

        self.remaining_label.setText(f"剩余时间：{time_str}")
        self.shutdown_time_label.setText(
            self._get_expected_time_label(self.end_time.toString("HH:mm:ss"))
        )
        self._update_tray_menu()

    # ======================== 提醒弹窗 ========================

    def _show_reminder(self, minutes_before: int):
        """弹出关机前提醒窗口（同一时间只存在一个弹窗）"""
        # 关闭已有的任何提醒弹窗，确保唯一性
        if self.reminder_dialog:
            try:
                self.reminder_dialog.close()
            except RuntimeError:
                pass
            self.reminder_dialog = None

        action = self._task_action_name
        dialog = ReminderDialog(
            minutes_before, self.delay_minutes, action,
            end_time=self.end_time, remaining_seconds=self.remaining_seconds,
            parent=self,
        )
        dialog.cancelled.connect(self._cancel_countdown)
        dialog.delayed.connect(self._delay_countdown)
        dialog.confirmed.connect(lambda: None)
        dialog.finished.connect(lambda: setattr(self, "reminder_dialog", None))

        self.reminder_dialog = dialog
        dialog.show()

    def _delay_countdown(self, minutes: int):
        """推迟关机"""
        seconds = minutes * 60
        self.remaining_seconds += seconds
        self.end_time = self.end_time.addSecs(seconds)
        self._update_display()

    # ======================== 游戏结束警告 ========================

    def _show_game_end_warning(self):
        """显示游戏结束警告：全屏程序已退出，倒计时后自动执行任务"""
        action = self._task_action_name
        secs = self.game_end_countdown
        # 系统托盘通知
        if hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage(
                "游戏模式 - 即将执行任务",
                f"检测到游戏/全屏程序已结束，系统将在{secs}秒后自动{action}。",
                QSystemTrayIcon.MessageIcon.Warning,
                10000,
            )

        # 非模态警告弹窗（不阻塞倒计时，置顶显示）
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("游戏模式 - 即将执行任务")
        msg.setText(f"检测到游戏/全屏程序已结束，系统将在{secs}秒后自动{action}。")
        msg.setInformativeText(f"如需取消{action}，请点击下方按钮。")
        cancel_btn = msg.addButton(f"取消{action}", QMessageBox.RejectRole)
        msg.setDefaultButton(cancel_btn)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        msg.setModal(False)
        msg.show()

        self.game_end_msg = msg

        def _on_btn_clicked(btn):
            if btn == cancel_btn:
                self._cancel_countdown()

        msg.buttonClicked.connect(_on_btn_clicked)

    # ======================== 执行系统任务 ========================

    def _execute_task(self):
        """按 task_type 执行系统任务（关机/重启/注销/睡眠/休眠）"""
        if self.is_shutting_down:
            return
        self.is_shutting_down = True
        self.timer.stop()
        self.is_counting = False
        self.action_btn.setText(self._get_start_btn_text())
        self.action_btn.setStyleSheet("")  # 恢复蓝色样式

        action = self._task_action_name
        # 保存 schedule_active 等状态，确保下次开机可恢复
        self._save_all_settings()
        try:
            subprocess.Popen(TASK_COMMANDS[self.task_type])
        except Exception as e:
            QMessageBox.critical(self, f"{action}失败", f"执行{action}命令时出错：\n{e}")
            self.is_shutting_down = False
            self._update_tray_menu()

    def _execute_shutdown(self):
        """始终执行关机（用于低电量等场景）"""
        if self.is_shutting_down:
            return
        self.is_shutting_down = True
        self.timer.stop()
        self.is_counting = False
        self.action_btn.setText(self._get_start_btn_text())
        self.action_btn.setStyleSheet("")

        try:
            subprocess.Popen(["shutdown", "/s", "/t", "0"])
        except Exception as e:
            QMessageBox.critical(self, "关机失败", f"执行关机命令时出错：\n{e}")
            self.is_shutting_down = False
            self._update_tray_menu()

    # ======================== 系统托盘 ========================

    def _setup_tray(self):
        """创建系统托盘图标和右键菜单"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self._create_tray_icon(), self)
        self.tray_menu = QMenu()

        # 状态栏（置顶，不可点击，倒计时运行时自动更新）
        self.task_status_action = self.tray_menu.addAction("任务未启动")
        self.task_status_action.setEnabled(False)
        self.time_remaining_action = self.tray_menu.addAction("")
        self.time_remaining_action.setEnabled(False)
        self.time_remaining_action.setVisible(False)
        self.tray_menu.addSeparator()

        self.show_action = self.tray_menu.addAction("打开主界面")
        self.start_action = self.tray_menu.addAction("开始定时关机")
        self.pause_action = self.tray_menu.addAction("暂停定时关机")
        self.tray_menu.addSeparator()
        self.quit_action = self.tray_menu.addAction("退出程序")

        self.tray_icon.setContextMenu(self.tray_menu)

        # 绑定信号
        self.show_action.triggered.connect(self._show_window)
        self.start_action.triggered.connect(self._start_countdown_from_tray)
        self.pause_action.triggered.connect(self._cancel_countdown)
        self.quit_action.triggered.connect(self._quit_app)
        self.tray_icon.activated.connect(self._on_tray_activated)

        self._update_tray_menu()
        self.tray_icon.show()

    def _create_tray_icon(self) -> QIcon:
        """绘制一个关机键样式的系统托盘图标"""
        return QIcon(self._make_shutdown_pixmap(32))

    @staticmethod
    def _make_shutdown_pixmap(size: int = 32) -> QPixmap:
        """绘制关机键图标像素图（蓝底白字关机符号）"""
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        m = max(2, size // 16)
        cx, cy = size // 2, size // 2
        r = size * 0.28
        pw = max(3, size // 12)

        # 蓝色圆形背景
        painter.setBrush(QColor("#339AF0"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(m, m, size - 2 * m, size - 2 * m)

        # 白色关机符号
        pen = QPen(QColor("white"), pw)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        painter.drawLine(cx, cy, cx, cy - int(r + pw))
        painter.drawArc(QRect(int(cx - r), int(cy - r), int(2 * r), int(2 * r)), 300 * 16, 300 * 16)

        painter.end()
        return pm

    def _show_window(self):
        """显示并激活主窗口"""
        self.show()
        self.raise_()
        self.activateWindow()

    def show_window_from_other_instance(self):
        """另一个实例启动时，本实例显示窗口"""
        self._show_window()

    def _on_tray_activated(self, reason):
        """托盘图标双击恢复窗口"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _update_tray_menu(self):
        """根据当前倒计时状态更新托盘菜单"""
        if not hasattr(self, 'tray_icon'):
            return

        action = self._task_action_name
        self.start_action.setText(f"开始定时{action}")
        self.pause_action.setText(f"暂停定时{action}")
        self.start_action.setEnabled(not self.is_counting)
        self.pause_action.setEnabled(self.is_counting)

        if self.is_counting:
            hours = self.remaining_seconds // 3600
            minutes = (self.remaining_seconds % 3600) // 60
            secs = self.remaining_seconds % 60
            end_str = self.end_time.toString("HH:mm:ss")
            self.task_status_action.setText(f"{action}任务 {end_str} 启动")
            self.task_status_action.setEnabled(True)
            self.time_remaining_action.setText(
                f"剩余时间 {hours:02d}:{minutes:02d}:{secs:02d}"
            )
            self.time_remaining_action.setEnabled(True)
            self.time_remaining_action.setVisible(True)
        else:
            self.task_status_action.setText(f"{action}任务未启动")
            self.task_status_action.setEnabled(False)
            self.time_remaining_action.setVisible(False)

    def _start_countdown_from_tray(self):
        """从托盘菜单启动倒计时"""
        if self.is_counting:
            return
        self._start_countdown()

    def _quit_app(self):
        """从托盘菜单退出程序"""
        self.timer.stop()
        self.is_counting = False
        if self.reminder_dialog and self.reminder_dialog.isVisible():
            self.reminder_dialog.close()
            self.reminder_dialog = None
        QApplication.quit()

    # ======================== 低电量自动关机 ========================

    def _setup_battery_monitor(self):
        """创建电池检测器（每 3 分钟检测一次）"""
        self.battery_monitor = BatteryMonitor()
        self.battery_timer = QTimer(self)
        self.battery_timer.setInterval(180000)  # 3 分钟
        self.battery_timer.timeout.connect(self._check_battery)
        self.battery_timer.start()
        self._check_battery()

    def _check_battery(self):
        """检测电池状态并更新显示，条件满足时弹出低电量警告"""
        status = self.battery_monitor.get_status()
        if status is None:
            self.battery_label.setText("当前电量：--")
            return

        percentage = status["percentage"]
        plugged = status["power_plugged"]

        # 更新显示
        if plugged:
            self.battery_label.setText(f"当前电量：{percentage:.0f}% (已接通)")
        else:
            self.battery_label.setText(f"当前电量：{percentage:.0f}% (未接通)")

        # 检查是否需要低电量警告
        if self.low_battery_enabled and not self.low_battery_disabled:
            if not plugged and percentage <= self.low_battery_threshold:
                if not self.low_battery_warned:
                    self._show_low_battery_warning(percentage)
            else:
                # 条件不满足时重置警告，以便下次再次触发
                self.low_battery_warned = False

    def _show_low_battery_warning(self, percentage: float):
        """弹出低电量警告弹窗"""
        self.low_battery_warned = True
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("低电量提醒")
        msg.setText(f"电池电量仅剩 {percentage:.0f}%，且未接通电源。")
        msg.setInformativeText("建议立即保存工作。")

        msg.addButton("暂不处理", QMessageBox.RejectRole)
        shutdown_btn = msg.addButton("立即关机", QMessageBox.AcceptRole)
        disable_btn = msg.addButton("本次禁用", QMessageBox.DestructiveRole)

        msg.exec()

        if msg.clickedButton() == shutdown_btn:
            self._execute_shutdown()
        elif msg.clickedButton() == disable_btn:
            self.low_battery_disabled = True
        # "暂不处理"：不做任何事，warned 标记保持为 True 避免重复打扰

    def _open_battery_settings(self):
        """打开低电量设置弹窗"""
        dialog = BatterySettingsDialog(
            self.low_battery_enabled,
            self.low_battery_threshold,
            self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.low_battery_enabled = dialog.is_enabled()
            self.low_battery_threshold = dialog.get_threshold()
            if not self.low_battery_enabled:
                self.low_battery_warned = False
                self.low_battery_disabled = False
            self._save_all_settings()

    # ======================== 配置持久化 ========================

    def _load_config(self):
        """从 JSON 文件恢复设置"""
        cfg = load_settings()

        timer = cfg.get("timer", {})
        if timer.get("mode") in ("倒计时模式", "预约模式", "预约关机"):
            raw = timer["mode"]
            self.current_mode = "预约模式" if raw == "预约关机" else raw
        if isinstance(timer.get("task_type"), str) and timer["task_type"] in TASK_TYPES:
            self.task_type = timer["task_type"]
        if isinstance(timer.get("countdown_minutes"), int):
            self.countdown_minutes = timer["countdown_minutes"]
        if isinstance(timer.get("target_time"), str):
            t = QTime.fromString(timer["target_time"], "HH:mm")
            if t.isValid():
                self.target_time = t
        if isinstance(timer.get("plan"), dict):
            plan = timer["plan"]
            sp = SchedulePlanDialog.default_plan()
            if plan.get("type") in ("once", "daily", "weekdays", "weekends", "weekly"):
                sp["type"] = plan["type"]
            if isinstance(plan.get("time"), str):
                t = QTime.fromString(plan["time"], "HH:mm")
                if t.isValid():
                    sp["time"] = t
            if isinstance(plan.get("weekly_enabled"), list) and len(plan["weekly_enabled"]) == 7:
                sp["weekly_enabled"] = plan["weekly_enabled"]
            if isinstance(plan.get("weekly_times"), list) and len(plan["weekly_times"]) == 7:
                times = []
                for ts in plan["weekly_times"]:
                    t = QTime.fromString(ts, "HH:mm")
                    times.append(t if t.isValid() else QTime(22, 0))
                sp["weekly_times"] = times
            self.schedule_plan = sp

        reminder = cfg.get("reminder", {})
        if isinstance(reminder.get("times"), list):
            self.reminder_times = [t for t in reminder["times"] if isinstance(t, int)]
        if isinstance(reminder.get("delay_minutes"), int):
            self.delay_minutes = reminder["delay_minutes"]

        battery = cfg.get("battery", {})
        if isinstance(battery.get("enabled"), bool):
            self.low_battery_enabled = battery["enabled"]
        if isinstance(battery.get("threshold"), int):
            self.low_battery_threshold = battery["threshold"]

        if isinstance(cfg.get("holiday_skip_enabled"), bool):
            self.holiday_skip_enabled = cfg["holiday_skip_enabled"]

        if isinstance(cfg.get("game_mode_enabled"), bool):
            self.game_mode_enabled = cfg["game_mode_enabled"]
        if isinstance(cfg.get("game_end_countdown"), int):
            self.game_end_countdown = cfg["game_end_countdown"]

        if isinstance(cfg.get("schedule_active"), bool):
            self.schedule_active = cfg["schedule_active"]

    def _save_all_settings(self):
        """将所有设置写入 JSON 文件"""
        save_settings(
            timer={
                "mode": self.current_mode,
                "task_type": self.task_type,
                "countdown_minutes": self.countdown_minutes,
                "target_time": self.target_time.toString("HH:mm"),
                "plan": {
                    "type": self.schedule_plan["type"],
                    "time": self.schedule_plan["time"].toString("HH:mm"),
                    "weekly_enabled": self.schedule_plan["weekly_enabled"],
                    "weekly_times": [
                        t.toString("HH:mm") for t in self.schedule_plan["weekly_times"]
                    ],
                },
            },
            reminder={
                "times": self.reminder_times,
                "delay_minutes": self.delay_minutes,
            },
            battery={
                "enabled": self.low_battery_enabled,
                "threshold": self.low_battery_threshold,
            },
            holiday_skip_enabled=self.holiday_skip_enabled,
            game_mode_enabled=self.game_mode_enabled,
            game_end_countdown=self.game_end_countdown,
            schedule_active=self.schedule_active,
        )
