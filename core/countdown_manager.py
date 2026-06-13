# --------------------------------------------------------------------------
# 文件：core/countdown_manager.py
# 用途：倒计时管理器——纯逻辑，与 UI 解耦
# 原则：不操作 UI，仅通过信号通信；支持睡眠/休眠暂停恢复
# --------------------------------------------------------------------------

from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal, QDateTime, QTime, QDate, Qt

from core.config_manager import load_settings, save_settings
from core.game_detector import is_fullscreen_app_running


class CountdownManager(QObject):
    """倒计时管理器

    职责：
    - 管理倒计时/预约模式的计时核心（QTimer 每秒触发）
    - 管理游戏模式推迟/警告逻辑
    - 管理提醒触发逻辑（弹窗时机，不操作弹窗本身）
    - 管理睡眠/休眠暂停恢复
    - 管理状态持久化（异常退出恢复）
    - 通过信号与 UI 层通信，零直接 UI 依赖

    信号：
        time_updated(remaining_seconds)          → UI 更新剩余时间显示
        reminder_needed(minutes_before)          → UI 打开提醒弹窗
        task_due(task_type)                      → Step3: 执行系统任务
        game_end_warning(task_type, seconds)     → UI 显示游戏结束警告
        state_changed(is_counting)               → UI 切换按钮文字/样式
        countdown_cancelled()                    → UI 重置相关状态
        countdown_started()                      → UI 更新后续处理
    """

    # ---- 信号 ----
    time_updated = Signal(int)
    reminder_needed = Signal(int)
    task_due = Signal(str)
    game_end_warning = Signal(str, int)
    state_changed = Signal(bool)
    countdown_cancelled = Signal()
    countdown_started = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # ======================== 任务配置 ========================

        self.current_mode = "预约模式"                    # 倒计时模式 / 预约模式
        self.countdown_minutes = 30
        self.target_time = QTime.currentTime().addSecs(3600)
        self.task_type = "shutdown"

        # ======================== 倒计时状态 ========================

        self.remaining_seconds = 0
        self.end_time = QDateTime()
        self.is_counting = False
        self.fired_reminders = set()                     # 已触发的提醒分钟数
        self.reminder_times = [1, 30]
        self.delay_minutes = 10

        # ======================== 游戏模式状态 ========================

        self.game_mode_enabled = False
        self.game_end_countdown = 60
        self.game_postponing = False
        self.game_end_warning_shown = False

        # ======================== 节假日 ========================

        self.holiday_skip_enabled = False
        self.holidays: set = set()
        self.holiday_periods: list = []

        # ======================== 预约计划 ========================

        self.schedule_plan = {
            "type":          "once",
            "time":          QTime(22, 0),
            "weekly_enabled": [False] * 7,
            "weekly_times":   [QTime(22, 0)] * 7,
        }
        self.schedule_active = False

        # ---- 加载节假日缓存（避免依赖 UI 线程） ----
        self._load_holiday_cache_from_config()

        # ======================== 每秒定时器 ========================

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._on_tick)

        # ======================== 暂停/恢复暂存 ========================

        self._paused_remaining = 0
        self._is_paused = False

    # ======================== 公共接口 ========================

    def start_countdown(
        self,
        mode: str,
        task_type: str,
        *,
        countdown_minutes: Optional[int] = None,
        target_time: Optional[QTime] = None,
        schedule_plan: Optional[dict] = None,
        reminder_times: Optional[list] = None,
        delay_minutes: Optional[int] = None,
    ) -> bool:
        """启动倒计时——纯逻辑，不操作 UI

        参数：
            mode:               "倒计时模式" / "预约模式"
            task_type:          任务类型（shutdown/restart/logout/sleep/hibernate）
            countdown_minutes:  倒计时分钟数（仅倒计时模式）
            target_time:        预约目标时间（仅预约模式）
            schedule_plan:      预约计划字典
            reminder_times:     提醒时间列表（如 [30, 10, 5, 1]）
            delay_minutes:      推迟分钟数

        返回：
            True  = 成功启动
            False = 参数错误（时间已过等）
        """
        self.current_mode = mode
        self.task_type = task_type

        if countdown_minutes is not None:
            self.countdown_minutes = countdown_minutes
        if target_time is not None:
            self.target_time = target_time
        if schedule_plan is not None:
            self.schedule_plan = schedule_plan
        if reminder_times is not None:
            self.reminder_times = reminder_times
        if delay_minutes is not None:
            self.delay_minutes = delay_minutes

        # ---- 计算总秒数 ----
        if mode == "倒计时模式":
            total_seconds = self.countdown_minutes * 60
        else:
            next_time = self._get_next_schedule_time()
            now = QDateTime.currentDateTime()
            if next_time <= now:
                return False
            total_seconds = now.secsTo(next_time)
            self.target_time = next_time.time()

        if total_seconds <= 0:
            return False

        # ---- 初始化倒计时状态 ----
        self.remaining_seconds = total_seconds
        self.end_time = QDateTime.currentDateTime().addSecs(total_seconds)
        self.fired_reminders.clear()
        self.game_postponing = False
        self.game_end_warning_shown = False

        self.is_counting = True
        self._is_paused = False
        self._paused_remaining = 0

        # 每周定时计划标记为活跃
        if mode == "预约模式" and self.schedule_plan["type"] == "weekly":
            self.schedule_active = True

        self.timer.start()

        # ---- 发送信号 ----
        self.state_changed.emit(True)
        self.time_updated.emit(self.remaining_seconds)
        self.countdown_started.emit()

        return True

    def cancel(self):
        """取消倒计时——纯逻辑，不操作 UI"""
        self.timer.stop()
        self.is_counting = False
        self.remaining_seconds = 0
        self.fired_reminders.clear()
        self.game_postponing = False
        self.game_end_warning_shown = False
        self.schedule_active = False
        self._is_paused = False
        self._paused_remaining = 0

        self.state_changed.emit(False)
        self.countdown_cancelled.emit()

    def cancel_game_end_warning(self):
        """取消游戏结束警告（用户在弹窗中点击取消时调用）"""
        self.cancel()

    def delay(self, minutes: int):
        """推迟倒计时，同时清除已触发的提醒记录"""
        seconds = minutes * 60
        self.remaining_seconds += seconds
        self.end_time = self.end_time.addSecs(seconds)
        self.fired_reminders.clear()
        self.time_updated.emit(self.remaining_seconds)

    def pause(self):
        """暂停倒计时（睡眠/休眠时调用）

        保存当前剩余时间，停止定时器。
        唤醒后通过 resume() 恢复。
        """
        if self.is_counting and not self._is_paused:
            self._paused_remaining = self.remaining_seconds
            self._is_paused = True
            self.timer.stop()

    def resume(self):
        """恢复倒计时（睡眠/休眠唤醒后调用）

        用已保存的剩余时间重建 end_time 并重新开始计时。
        """
        if self._is_paused and self._paused_remaining > 0:
            self.remaining_seconds = self._paused_remaining
            self.end_time = QDateTime.currentDateTime().addSecs(self._paused_remaining)
            self._is_paused = False
            self._paused_remaining = 0
            self.is_counting = True
            self.timer.start()
            self.time_updated.emit(self.remaining_seconds)
            self.state_changed.emit(True)

    def get_remaining(self) -> int:
        """获取当前剩余秒数"""
        return self.remaining_seconds

    def is_running(self) -> bool:
        """倒计时是否正在运行"""
        return self.is_counting

    # ======================== 核心计时逻辑 ========================

    def _on_tick(self):
        """每秒执行一次（QTimer 回调）"""
        if not self.is_counting:
            return

        # 用 end_time 重新计算剩余秒数，消除 timer 累积误差
        remaining = QDateTime.currentDateTime().secsTo(self.end_time)
        self.remaining_seconds = remaining if remaining >= 0 else 0

        if self.remaining_seconds <= 0:
            self._handle_timeout()
            return

        # ---- 提醒检测（仅非推迟期间） ----
        if not self.game_postponing:
            for reminder_min in self.reminder_times:
                reminder_sec = reminder_min * 60
                if self.remaining_seconds <= reminder_sec and reminder_min not in self.fired_reminders:
                    self.reminder_needed.emit(reminder_min)
                    self.fired_reminders.add(reminder_min)

        self.time_updated.emit(self.remaining_seconds)

    def _handle_timeout(self):
        """倒计时到 0 时的策略选择"""
        # ① 游戏模式：警告已显示过 → 直接执行任务
        if self.game_mode_enabled and self.game_end_warning_shown:
            self.timer.stop()
            self.is_counting = False
            self.state_changed.emit(False)
            self.task_due.emit(self.task_type)
            return

        # ② 游戏模式：全屏程序运行中 → 自动推迟 15 分钟
        if self.game_mode_enabled and is_fullscreen_app_running():
            self.remaining_seconds = 15 * 60
            self.game_postponing = True
            self.end_time = QDateTime.currentDateTime().addSecs(15 * 60)
            self.time_updated.emit(self.remaining_seconds)
            return

        # ③ 游戏模式：游戏刚结束（之前推迟过）→ 显示警告，倒计时后执行
        if self.game_mode_enabled and self.game_postponing:
            self.game_postponing = False
            self.game_end_warning_shown = True
            self.remaining_seconds = self.game_end_countdown
            self.end_time = QDateTime.currentDateTime().addSecs(self.game_end_countdown)
            self.game_end_warning.emit(self.task_type, self.game_end_countdown)
            self.time_updated.emit(self.remaining_seconds)
            return

        # ④ 正常 → 执行任务
        self.timer.stop()
        self.is_counting = False
        self.state_changed.emit(False)
        self.task_due.emit(self.task_type)

    # ======================== 预约时间计算 ========================

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

    def _is_holiday_date(self, d: QDate) -> bool:
        """判断指定日期是否为法定节假日（受 holiday_skip_enabled 开关控制）"""
        if not self.holiday_skip_enabled:
            return False
        return d.toString("yyyy-MM-dd") in self.holidays

    # ======================== 状态持久化 ========================

    def save_state(self):
        """保存当前倒计时状态到配置文件

        用于：
        - 异常退出后恢复（异常崩溃时丢失，但定时保存可减少损失）
        - 正常退出前保存
        """
        save_settings(
            countdown_state={
                "is_counting":          self.is_counting,
                "remaining_seconds":    self.remaining_seconds,
                "end_time":             self.end_time.toString(Qt.ISODate)
                                        if self.end_time.isValid() else "",
                "task_type":            self.task_type,
                "current_mode":         self.current_mode,
                "schedule_active":      self.schedule_active,
                "game_postponing":      self.game_postponing,
                "game_end_warning_shown": self.game_end_warning_shown,
                "paused_remaining":     self._paused_remaining,
                "is_paused":            self._is_paused,
            }
        )

    def load_state(self) -> bool:
        """从配置文件恢复倒计时状态

        返回：
            True  = 找到未完成的任务并恢复
            False = 无待恢复任务
        """
        cfg = load_settings()
        state = cfg.get("countdown_state", {})
        if not state or not state.get("is_counting", False):
            return False

        self.task_type = state.get("task_type", self.task_type)
        self.current_mode = state.get("current_mode", self.current_mode)
        self.game_postponing = state.get("game_postponing", False)
        self.game_end_warning_shown = state.get("game_end_warning_shown", False)
        self.schedule_active = state.get("schedule_active", False)
        self._paused_remaining = state.get("paused_remaining", 0)
        self._is_paused = state.get("is_paused", False)

        end_time_str = state.get("end_time", "")
        if end_time_str:
            dt = QDateTime.fromString(end_time_str, Qt.ISODate)
            if dt.isValid():
                remaining = QDateTime.currentDateTime().secsTo(dt)
                if remaining > 0:
                    self.remaining_seconds = remaining
                    self.end_time = dt
                    self.is_counting = True
                    self.fired_reminders.clear()
                    self.timer.start()
                    self.state_changed.emit(True)
                    self.time_updated.emit(remaining)
                    return True

        return False

    def clear_state(self):
        """清除配置文件中的倒计时状态（任务完成或取消时调用）"""
        save_settings(countdown_state={})

    # ======================== 节假日辅助 ========================

    def _load_holiday_cache_from_config(self):
        """从配置文件加载节假日缓存

        纯数据读取，不涉及网络请求（网络请求仍由 UI 层触发）。
        """
        cfg = load_settings()
        cache = cfg.get("holiday_cache", {})
        if isinstance(cache, dict):
            self.holidays = set(cache.get("dates", []))
            self.holiday_periods = cache.get("periods", [])

    def set_holidays(self, holidays: set, holiday_periods: list):
        """供 MainWindow 在节假日数据更新后同步给 CountdownManager"""
        self.holidays = holidays
        self.holiday_periods = holiday_periods

    def set_holiday_skip_enabled(self, enabled: bool):
        """设置节假日跳过开关"""
        self.holiday_skip_enabled = enabled
