# --------------------------------------------------------------------------
# 文件：core/battery_monitor.py
# 用途：检测笔记本电池电量与电源状态（依赖 psutil）
# --------------------------------------------------------------------------

import psutil


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
