# --------------------------------------------------------------------------
# 文件：core/network_repair/models.py
# 用途：网络诊断与修复模块的数据模型
# 说明：纯数据类，不依赖 Qt 或任何 GUI 框架，可独立测试
# --------------------------------------------------------------------------

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class DiagnosisLevel(Enum):
    """单项诊断级别"""
    OK = "正常"
    WARNING = "异常"
    INFO = "信息"


class NetworkHealthLevel(Enum):
    """整体网络健康等级（顶部卡片用）"""
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class DiagnosisItem:
    """单项诊断结果"""
    name: str = ""                          # 诊断项目名称（如"网络适配器"）
    status: str = ""                        # 当前状态简述
    level: DiagnosisLevel = DiagnosisLevel.INFO  # 诊断级别
    detail: str = ""                        # 详细说明 / 额外信息
    suggestion: str = ""                    # 针对此问题的修复建议


@dataclass
class DiagnosisReport:
    """完整诊断报告"""
    items: List[DiagnosisItem] = field(default_factory=list)
    health_level: NetworkHealthLevel = NetworkHealthLevel.HEALTHY
    conclusion: str = ""                    # 检测结论
    recommendation: str = ""                # 推荐方案
    timestamp: str = ""                     # 检测时间

    @property
    def ok_count(self) -> int:
        """正常项数量"""
        return sum(1 for i in self.items if i.level == DiagnosisLevel.OK)

    @property
    def warning_count(self) -> int:
        """异常项数量"""
        return sum(1 for i in self.items if i.level == DiagnosisLevel.WARNING)

    @property
    def info_count(self) -> int:
        """信息项数量"""
        return sum(1 for i in self.items if i.level == DiagnosisLevel.INFO)

    def to_text(self) -> str:
        """导出诊断报告为纯文本（剪贴板 / 日志用）"""
        lines = [
            "=" * 48,
            "          网 络 诊 断 报 告",
            "=" * 48,
            f"检测时间：{self.timestamp}",
            f"健康状态：{self._health_text()}",
            "-" * 48,
            "",
        ]

        for item in self.items:
            if item.level == DiagnosisLevel.OK:
                icon = "✔"
            elif item.level == DiagnosisLevel.WARNING:
                icon = "✖"
            else:
                icon = "ℹ"
            lines.append(f"  {icon}  {item.name}：{item.status}")
            if item.detail:
                lines.append(f"      详情：{item.detail}")
            lines.append("")

        lines.append("-" * 48)
        lines.append(f"结论：{self.conclusion}")
        lines.append(f"建议：{self.recommendation}")
        lines.append(f"（正常 {self.ok_count} 项 | 异常 {self.warning_count} 项 | 信息 {self.info_count} 项）")
        lines.append("=" * 48)
        return "\n".join(lines)

    def _health_text(self) -> str:
        mapping = {
            NetworkHealthLevel.HEALTHY: "网络正常",
            NetworkHealthLevel.WARNING: "存在轻微异常",
            NetworkHealthLevel.ERROR: "网络配置异常",
        }
        return mapping.get(self.health_level, "未知")


@dataclass
class RepairProgress:
    """修复进度（UI 进度条更新用）"""
    current_step: str = ""                  # 当前步骤名称
    completed: int = 0                      # 已完成步骤数量
    total: int = 0                          # 总步骤数量
    log: str = ""                           # 实时执行日志文字


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: str = ""
    action: str = ""                        # 操作类型：诊断 / 修复 / 步骤 / 异常 / 导出
    result: str = ""                        # 结果：成功 / 失败 / 完成
    detail: str = ""                        # 详细信息
