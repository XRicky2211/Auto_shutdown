# --------------------------------------------------------------------------
# 文件：core/battery_monitor.py
# 用途：检测笔记本电池电量与电源状态（依赖 psutil）
# --------------------------------------------------------------------------

import psutil
from psutil import POWER_TIME_UNLIMITED, POWER_TIME_UNKNOWN


class BatteryMonitor:
    """笔记本电池状态检测"""

    @staticmethod
    def get_status():
        """
        获取当前电池状态。

        返回：
            {
                "percentage":   float,   # 当前电量百分比 0~100
                "power_plugged": bool,    # True=接通电源，False=电池供电
            }
            如果设备没有电池（台式机），返回 None。
        """
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        return {
            "percentage": battery.percent,
            "power_plugged": battery.power_plugged,
        }

    @staticmethod
    def get_battery_info():
        """
        获取扩展的电池信息（包含 psutil 原生的 secsleft 字段）。

        返回：
            {
                "percentage":    float,   # 当前电量百分比 0~100
                "power_plugged": bool,    # True=接通电源
                "secsleft":      int,     # psutil 预估剩余秒数
            }
            如果设备没有电池，返回 None。

        secsleft 取值说明：
            - POWER_TIME_UNLIMITED  (-1)：接通电源
            - POWER_TIME_UNKNOWN    (-2)：无法预估
            - 其他正数：预估剩余秒数
        """
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        return {
            "percentage": battery.percent,
            "power_plugged": battery.power_plugged,
            "secsleft": battery.secsleft,
        }
