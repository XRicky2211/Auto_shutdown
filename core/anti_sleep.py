# --------------------------------------------------------------------------
# 文件：core/anti_sleep.py
# 用途：防休眠管理器——倒计时任务运行中阻止系统进入睡眠/锁屏等状态
# 原理：通过 Windows SetThreadExecutionState API 向系统声明当前忙碌
# --------------------------------------------------------------------------

import ctypes
from ctypes import wintypes

# ---- Windows 执行状态标志 ----
ES_CONTINUOUS = 0x80000000       # 持续生效，直到下次调用
ES_SYSTEM_REQUIRED = 0x00000001  # 阻止系统进入睡眠
ES_DISPLAY_REQUIRED = 0x00000002 # 阻止显示器自动关闭
ES_AWAYMODE_REQUIRED = 0x00000040 # 离开模式（Win7+，仅媒体场景）

# kernel32 的 SetThreadExecutionState
_set_execution_state = ctypes.windll.kernel32.SetThreadExecutionState
_set_execution_state.argtypes = [wintypes.DWORD]
_set_execution_state.restype = wintypes.DWORD


class AntiSleepManager:
    """防休眠管理器

    在倒计时任务运行期间调用 enable() 阻止系统进入睡眠/锁屏，
    任务结束后调用 disable() 恢复系统默认电源策略。

    注意：
    - 仅在 Windows 下生效，非 Windows 系统调用无效果
    - 阻止的是"空闲睡眠"，不阻止用户手动点击睡眠
    - block_display=True 时同时阻止显示器熄灭（会增加耗电）
    """

    def __init__(self):
        self._enabled = False      # 当前是否持有执行状态
        self._block_display = False  # 配置：是否阻止显示器关闭

    # ======================== 公共接口 ========================

    def enable(self, block_display: bool = False):
        """开启防休眠模式

        参数：
            block_display: 是否同时阻止显示器自动关闭
                           （默认 False，仅阻止睡眠，省电）
        """
        if self._enabled and self._block_display == block_display:
            return  # 状态未变，不重复调用

        self._block_display = block_display
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        if block_display:
            flags |= ES_DISPLAY_REQUIRED

        _set_execution_state(flags)
        self._enabled = True

    def disable(self):
        """关闭防休眠模式，恢复系统默认电源策略"""
        if not self._enabled:
            return

        # 清除所有标志：只传 ES_CONTINUOUS 即释放之前设置的所有标志
        _set_execution_state(ES_CONTINUOUS)
        self._enabled = False
        self._block_display = False

    def update(self, block_display: bool):
        """更新防休眠参数（不改变启用/禁用状态）

        用于用户在倒计时运行中修改配置时，实时生效。
        若当前未启用，不执行任何操作。
        """
        if not self._enabled:
            return
        self._block_display = block_display
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        if block_display:
            flags |= ES_DISPLAY_REQUIRED
        _set_execution_state(flags)

    @property
    def is_active(self) -> bool:
        """防休眠是否正在生效"""
        return self._enabled
