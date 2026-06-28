# --------------------------------------------------------------------------
# 文件：core/network_repair/__init__.py
# 用途：网络诊断与修复模块的统一导出
# 说明：外部代码通过 from core.network_repair import ... 访问
# --------------------------------------------------------------------------

from .models import (
    DiagnosisItem,
    DiagnosisReport,
    DiagnosisLevel,
    NetworkHealthLevel,
    RepairProgress,
    LogEntry,
)
from .diagnosis_service import (
    run_full_diagnosis,
    quick_check_after_repair,
)
from .repair_service import RepairService, ELEVATION_REQUIRED
from .log_service import (
    write_log,
    write_log_entry,
    read_log_lines,
    get_log_path,
    export_logs,
)

__all__ = [
    # 模型
    "DiagnosisItem",
    "DiagnosisReport",
    "DiagnosisLevel",
    "NetworkHealthLevel",
    "RepairProgress",
    "LogEntry",
    # 诊断
    "run_full_diagnosis",
    "quick_check_after_repair",
    # 修复
    "RepairService",
    "ELEVATION_REQUIRED",
    # 日志
    "write_log",
    "write_log_entry",
    "read_log_lines",
    "get_log_path",
    "export_logs",
]
