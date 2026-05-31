# --------------------------------------------------------------------------
# 文件：core/battery_analyzer.py
# 用途：记录电池电量历史采样点，计算放电速率，预估剩余使用时间
# --------------------------------------------------------------------------

import time
from typing import Optional


class BatteryAnalyzer:
    """电池数据分析器

    维护最近一段时间的电量采样历史，用于：
    - 计算每分钟平均放电速率
    - 预估剩余可用时间
    - 生成中文趋势描述文本

    采样点格式：(timestamp: float, percentage: float)
    """

    def __init__(self, max_samples: int = 15):
        """
        参数：
            max_samples: 最多保留的采样点数（默认 15，对应约 45 分钟数据窗口）
        """
        self._samples: list = []
        self._max_samples = max_samples

    # ======================== 公开接口 ========================

    def record(self, percentage: float, power_plugged: bool) -> None:
        """记录一次电量采样

        若接通电源或电量上升，说明在充电，清空历史记录。
        否则追加采样点，并截断到最大样本数。

        参数：
            percentage:     当前电量百分比
            power_plugged:  是否接通电源
        """
        now = time.time()

        if power_plugged:
            self.clear()
            return

        # 如果最近有采样点且电量在上升，视为正在充电，清空历史
        if self._samples and percentage > self._samples[-1][1]:
            self.clear()
            # 把当前点作为新历史的第一个采样点
            self._samples.append((now, percentage))
            return

        self._samples.append((now, percentage))

        # 截断到 max_samples
        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples:]

    def drain_per_minute(self) -> Optional[float]:
        """计算每分钟平均放电速率（% / min）

        基于最近两个采样点计算瞬时速率。
        返回 None 的情况：
        - 采样点不足 2 个
        - 时间差为 0（不可能，但防御性处理）

        返回：
            正数表示每分钟下降的百分比，负数表示充电
        """
        if len(self._samples) < 2:
            return None

        newest = self._samples[-1]
        oldest = self._samples[-2]
        dt = newest[0] - oldest[0]  # 秒

        if dt <= 0:
            return None

        dp = oldest[1] - newest[1]  # 正数 = 放电
        return dp / (dt / 60.0)

    def estimate_remaining_minutes(self, percentage: float) -> Optional[int]:
        """预估剩余可用分钟数

        参数：
            percentage: 当前电量百分比

        返回：
            预估分钟数（向下取整），或 None（无法预估）
        """
        rate = self.drain_per_minute()
        if rate is None or rate <= 0:
            return None

        minutes = percentage / rate
        return max(1, int(round(minutes)))

    def trend_text(self, percentage: float) -> str:
        """返回中文趋势描述文本

        返回：
            - "预计可用 XX 分钟"
            - "预计可用 X 小时 XX 分钟"
            - "数据收集中..."
            - "电源已接通"
        """
        # 没有采样点时，判断是否在充电
        if not self._samples:
            return "数据收集中..."

        rate = self.drain_per_minute()
        if rate is None:
            return "数据收集中..."

        # 放电速率小于等于 0，说明在充电
        if rate <= 0:
            return "电源已接通"

        minutes = self.estimate_remaining_minutes(percentage)
        if minutes is None:
            return "数据收集中..."

        if minutes < 60:
            return f"预计可用 {minutes} 分钟"
        else:
            h = minutes // 60
            m = minutes % 60
            return f"预计可用 {h} 小时 {m} 分钟"

    def clear(self) -> None:
        """清空所有采样历史"""
        self._samples.clear()
