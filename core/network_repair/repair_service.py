# --------------------------------------------------------------------------
# 文件：core/network_repair/repair_service.py
# 用途：网络修复服务——一键修复和高级修复
# 说明：纯逻辑模块，不依赖 Qt；通过回调函数向 UI 报告进度；
#       修复前自动检测管理员权限，无权限时返回提权请求
# --------------------------------------------------------------------------

import ctypes
import os
import subprocess
import sys
from typing import Callable, Optional, Tuple

from .models import RepairProgress, DiagnosisReport
from .diagnosis_service import quick_check_after_repair
from .log_service import write_log

# ---- Windows 创建标志 ----
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# ---- 权限状态 ----
ELEVATION_REQUIRED = "elevation_required"


class RepairService:
    """网络修复服务

    职责：
        - 一键修复（三阶段，可中断）
        - 高级修复
        - 管理员权限检测与提权
        - 通过回调报告进度

    使用方式：
        service = RepairService()
        service.one_click_repair(progress_callback=on_progress)
    """

    def __init__(self):
        """初始化修复服务：重置取消标记和适配器名"""
        self._cancelled = False
        self._active_adapter_name: str = ""

    # ======================== 工具方法 ========================

    @staticmethod
    def is_admin() -> bool:
        """检测当前是否具有管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except (AttributeError, OSError):
            return False

    @staticmethod
    def request_elevation() -> bool:
        """请求以管理员权限重启当前进程

        shell32.ShellExecuteW(runas) 启动自身，然后退出当前进程。
        使用 --restart-as-admin 标记让重启后的实例知道自己是被提权的。
        返回 False 表示用户取消了 UAC 提示或提权失败。
        """
        try:
            # 构建额外参数：提权标记 + 原始参数
            extra_params = "--restart-as-admin"
            if len(sys.argv) > 1:
                extra_params += " " + " ".join(
                    a for a in sys.argv[1:] if a != "--restart-as-admin"
                )

            if getattr(sys, "frozen", False):
                # 打包为 exe：直接以 exe 本身作为目标
                executable = sys.executable
                params = extra_params
            else:
                # 开发模式：python.exe main.py 形式
                executable = sys.executable
                params = f'"{os.path.abspath(sys.argv[0])}" {extra_params}'

            # ShellExecuteW with "runas" — Windows 标准提权方式
            result = ctypes.windll.shell32.ShellExecuteW(
                None,        # hwnd
                "runas",     # verb — 请求管理员权限
                executable,  # file
                params,      # parameters
                None,        # directory
                1,           # SW_SHOWNORMAL
            )
            # ShellExecuteW 返回值 > 32 表示成功
            return result > 32
        except Exception as e:
            write_log("提权", "失败", str(e))
            return False

    def cancel(self):
        """取消正在进行的修复"""
        self._cancelled = True

    def reset_cancel(self):
        """重置取消状态（准备新的修复）"""
        self._cancelled = False

    # ======================== 底层命令执行 ========================

    @staticmethod
    def _run_cmd(cmd: list, timeout: int = 30) -> Tuple[bool, str]:
        """执行系统命令，返回 (成功与否, stdout)"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=_CREATE_NO_WINDOW,
            )
            ok = result.returncode == 0
            output = result.stdout or result.stderr or ""
            return ok, output.strip()
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except (OSError, FileNotFoundError) as e:
            return False, str(e)

    @staticmethod
    def _check_internet() -> bool:
        """简易 Internet 可达性检测"""
        try:
            out1 = subprocess.run(
                ["ping", "-n", "1", "-w", "2000", "8.8.8.8"],
                capture_output=True, text=True, timeout=5,
                creationflags=_CREATE_NO_WINDOW,
            ).stdout
            if "TTL=" in out1:
                return True
            out2 = subprocess.run(
                ["ping", "-n", "1", "-w", "2000", "baidu.com"],
                capture_output=True, text=True, timeout=5,
                creationflags=_CREATE_NO_WINDOW,
            ).stdout
            return "TTL=" in out2
        except Exception:
            return False

    # ======================== 一键修复 ========================

    def one_click_repair(
        self,
        progress_callback: Optional[Callable[[RepairProgress], None]] = None,
    ) -> Tuple[bool, Optional[DiagnosisReport]]:
        """一键修复——三阶段逐级执行

        返回 (是否完全修复成功, 修复后检测报告)：
            - 完全修复成功：True, 健康的报告
            - 部分修复成功：False, 带异常的报告
            - 需要提权：False 且触发 ELEVATION_REQUIRED
        """
        self.reset_cancel()

        # ---- 权限检查 ----
        admin = self.is_admin()
        if not admin:
            write_log("一键修复", "需管理员权限", "检测到无管理员权限，尝试提权")
            return ELEVATION_REQUIRED, None

        write_log("一键修复", "开始", "以管理员权限执行一键修复")

        # ---- 第一阶段：代理清理（低风险） ----
        phase1_steps = [
            ("关闭系统代理", self._disable_system_proxy),
            ("恢复 PAC 设置", self._clear_pac),
            ("重置 WinHTTP 代理", self._reset_winhttp_proxy),
            ("刷新 DNS 缓存", self._flush_dns),
        ]
        ok = self._run_phase(
            "第一阶段：清理代理配置",
            phase1_steps,
            progress_callback,
        )

        if not self._cancelled and (ok or self._check_internet()):
            write_log("一键修复", "第一阶段完成", "代理清理完成，网络已恢复")
            report = quick_check_after_repair()
            if report.health_level.value == "healthy":
                self._report_progress(
                    progress_callback, "修复完成", 99, 99
                )
                return True, report

        # ---- 第二阶段：Winsock/TCP 重置（中等风险） ----
        phase2_steps = [
            ("重置 Winsock", self._reset_winsock),
            ("重置 TCP/IP", self._reset_tcpip),
            ("重新获取 DHCP", self._renew_dhcp),
            ("刷新 DNS 缓存", self._flush_dns),
        ]
        ok = self._run_phase(
            "第二阶段：重置网络栈",
            phase2_steps,
            progress_callback,
        )

        if not self._cancelled and (ok or self._check_internet()):
            write_log("一键修复", "第二阶段完成", "网络栈重置完成")
            report = quick_check_after_repair()
            if report.health_level.value == "healthy":
                self._report_progress(
                    progress_callback, "修复完成", 99, 99
                )
                return True, report

        # ---- 第三阶段：重启网络适配器（高风险） ----
        phase3_steps = [
            ("检测网络适配器", self._detect_active_adapter),
            ("重启网络适配器", self._restart_adapter),
            ("刷新 DNS", self._flush_dns),
        ]
        if not self._cancelled:
            self._run_phase(
                "第三阶段：重启网络适配器",
                phase3_steps,
                progress_callback,
            )

        self._report_progress(
            progress_callback, "修复完成，部分异常仍存在", 99, 99,
        )
        report = quick_check_after_repair()
        write_log(
            "一键修复",
            "部分失败",
            f"经三阶段修复仍有 {report.warning_count} 项异常",
        )
        return False, report

    # ======================== 高级修复 ========================

    def advanced_repair(
        self,
        progress_callback: Optional[Callable[[RepairProgress], None]] = None,
    ) -> Tuple[bool, Optional[DiagnosisReport]]:
        """高级修复——执行全部重置操作

        返回同 one_click_repair。
        """
        self.reset_cancel()

        if not self.is_admin():
            write_log("高级修复", "需管理员权限")
            return ELEVATION_REQUIRED, None

        write_log("高级修复", "开始", "执行完整网络重置")

        steps = [
            ("重置 Winsock", self._reset_winsock),
            ("重置 TCP/IP", self._reset_tcpip),
            ("重置 WinHTTP 代理", self._reset_winhttp_proxy),
            ("刷新 DNS 缓存", self._flush_dns),
            ("释放 IP 地址", self._release_ip),
            ("重新获取 IP 地址", self._renew_ip),
            ("重启网络适配器", self._restart_adapter),
            ("重置 IPv4 配置", self._reset_ipv4),
            ("重置 IPv6 配置", self._reset_ipv6),
        ]

        self._run_phase("高级修复执行中", steps, progress_callback)

        if self._cancelled:
            write_log("高级修复", "已取消")
            return False, None

        self._report_progress(
            progress_callback, "高级修复完成", 99, 99,
        )
        report = quick_check_after_repair()
        ok = report.health_level.value == "healthy"
        write_log(
            "高级修复", "成功" if ok else "部分失败",
            (
                f"正常 {report.ok_count} 项, "
                f"异常 {report.warning_count} 项"
            ),
        )
        return ok, report

    # ======================== 修复步骤单元 ========================

    @staticmethod
    def _disable_system_proxy() -> bool:
        """关闭系统代理（注册表）"""
        try:
            import winreg
            key_path = (
                r"Software\Microsoft\Windows\CurrentVersion"
                r"\Internet Settings"
            )
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(
                    key, "ProxyEnable", 0, winreg.REG_DWORD, 0
                )
            return True
        except Exception as e:
            write_log("关闭系统代理", "失败", str(e))
            return False

    @staticmethod
    def _clear_pac() -> bool:
        """清除 PAC 自动代理脚本"""
        try:
            import winreg
            key_path = (
                r"Software\Microsoft\Windows\CurrentVersion"
                r"\Internet Settings"
            )
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(
                    key, "AutoConfigURL", 0, winreg.REG_SZ, ""
                )
            return True
        except Exception as e:
            write_log("清除 PAC", "失败", str(e))
            return False

    @staticmethod
    def _reset_winhttp_proxy() -> bool:
        """重置 WinHTTP 代理"""
        ok, out = RepairService._run_cmd(
            ["netsh", "winhttp", "reset", "proxy"]
        )
        if not ok:
            write_log("重置 WinHTTP", "失败", out)
        return ok

    @staticmethod
    def _flush_dns() -> bool:
        """刷新 DNS 缓存"""
        ok, out = RepairService._run_cmd(
            ["ipconfig", "/flushdns"]
        )
        if not ok:
            write_log("刷新 DNS", "失败", out)
        return ok

    @staticmethod
    def _reset_winsock() -> bool:
        """重置 Winsock"""
        ok, out = RepairService._run_cmd(
            ["netsh", "winsock", "reset"]
        )
        if not ok:
            write_log("重置 Winsock", "失败", out)
        return ok

    @staticmethod
    def _reset_tcpip() -> bool:
        """重置 TCP/IP 堆栈"""
        ok, out = RepairService._run_cmd(
            ["netsh", "int", "ip", "reset"]
        )
        if not ok:
            write_log("重置 TCP/IP", "失败", out)
        return ok

    @staticmethod
    def _renew_dhcp() -> bool:
        """重新获取 DHCP 租约"""
        ok, out = RepairService._run_cmd(
            ["ipconfig", "/renew"], timeout=30
        )
        if not ok:
            write_log("DHCP 更新", "失败", out)
        return ok

    @staticmethod
    def _release_ip() -> bool:
        """释放 IP 地址"""
        ok, out = RepairService._run_cmd(
            ["ipconfig", "/release"]
        )
        if not ok:
            write_log("释放 IP", "失败", out)
        return ok

    @staticmethod
    def _renew_ip() -> bool:
        """重新获取 IP 地址"""
        ok, out = RepairService._run_cmd(
            ["ipconfig", "/renew"], timeout=30
        )
        if not ok:
            write_log("重新获取 IP", "失败", out)
        return ok

    def _detect_active_adapter(self) -> bool:
        """检测当前活跃的网卡名（存储供重启用）"""
        try:
            ps_out = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "(Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} "
                    "| Select-Object -First 1).Name",
                ],
                capture_output=True, text=True, timeout=10,
                creationflags=_CREATE_NO_WINDOW,
            ).stdout.strip()
            if ps_out:
                self._active_adapter_name = ps_out
                return True
        except Exception as e:
            write_log("检测网卡", "失败", str(e))
        return False

    def _restart_adapter(self) -> bool:
        """重启活跃的网卡"""
        name = self._active_adapter_name
        if not name:
            # 尝试直接重启所有 Up 网卡
            ok, out = RepairService._run_cmd(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} "
                    "| Restart-NetAdapter -Confirm:$false",
                ],
                timeout=30,
            )
            if not ok:
                write_log("重启网卡", "失败", out)
            return ok

        ok, out = RepairService._run_cmd(
            [
                "powershell", "-NoProfile", "-Command",
                f"Restart-NetAdapter -Name '{name}' -Confirm:$false",
            ],
            timeout=30,
        )
        if not ok:
            write_log("重启网卡", "失败", out)
        return ok

    @staticmethod
    def _reset_ipv4() -> bool:
        """重置 IPv4 配置"""
        ok1, _ = RepairService._run_cmd(
            ["netsh", "int", "ipv4", "reset"]
        )
        ok2, _ = RepairService._run_cmd(
            ["netsh", "int", "ip", "reset", "reset.log"]
        )
        return ok1 and ok2

    @staticmethod
    def _reset_ipv6() -> bool:
        """重置 IPv6 配置"""
        ok, out = RepairService._run_cmd(
            ["netsh", "int", "ipv6", "reset"]
        )
        if not ok:
            write_log("重置 IPv6", "失败", out)
        return ok

    # ======================== 阶段执行器 ========================

    def _run_phase(
        self,
        phase_name: str,
        steps: list,
        callback: Optional[Callable[[RepairProgress], None]],
    ) -> bool:
        """依次执行一组修复步骤

        参数：
            phase_name: 阶段名称
            steps: [(描述, callable), ...]
        返回：所有步骤是否全部成功
        """
        total = len(steps)
        all_ok = True
        for i, (desc, func) in enumerate(steps):
            if self._cancelled:
                return False

            self._report_progress(callback, desc, i, total)

            try:
                step_ok = func()
                if step_ok:
                    write_log("修复步骤", "成功", desc)
                else:
                    write_log("修复步骤", "失败", desc)
                all_ok = all_ok and step_ok
            except Exception as e:
                write_log("修复步骤", "异常", f"{desc}: {e}")
                all_ok = False

        # 阶段完成
        self._report_progress(
            callback, f"{phase_name} 完成", total, total,
        )
        return all_ok

    @staticmethod
    def _report_progress(
        callback: Optional[Callable[[RepairProgress], None]],
        step: str,
        completed: int,
        total: int,
    ):
        """触发进度回调"""
        if callback:
            try:
                callback(
                    RepairProgress(
                        current_step=step,
                        completed=completed,
                        total=total,
                        log=f"正在{step}...",
                    )
                )
            except Exception:
                pass
