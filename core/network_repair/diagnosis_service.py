# --------------------------------------------------------------------------
# 文件：core/network_repair/diagnosis_service.py
# 用途：网络诊断服务——执行完整的网络状态检测
# 说明：纯逻辑模块，不依赖 Qt；支持普通权限运行；
#       使用 subprocess.run 执行系统命令，所有异常捕获后写入日志
# --------------------------------------------------------------------------

import os
import subprocess
import sys
import socket
import re
from datetime import datetime

from .models import (
    DiagnosisItem, DiagnosisReport, DiagnosisLevel, NetworkHealthLevel,
)
from .log_service import write_log


# ---- Windows 控制台创建标志 ----
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _run(cmd: list, timeout: int = 10) -> str:
    """执行系统命令并返回 stdout（异常时返回空字符串）
    统一使用 CREATE_NO_WINDOW 避免弹窗。
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, OSError, UnicodeDecodeError, FileNotFoundError):
        return ""


def _run_powershell(script: str) -> str:
    """执行 PowerShell 命令并返回 stdout"""
    return _run(
        ["powershell", "-NoProfile", "-Command", script],
        timeout=15,
    )


# ====================================================================
# 网络诊断函数
# ====================================================================


def diagnose_network_adapter() -> DiagnosisItem:
    """① 检测网络适配器是否正常（检查有线/WiFi 适配器状态）"""
    item = DiagnosisItem(name="网络适配器")
    try:
        # 使用 PowerShell 获取更准确的适配器状态
        output = _run_powershell(
            "Get-NetAdapter | Where-Object {$_.Status -ne 'NotPresent'} "
            "| Select-Object Name, Status, LinkSpeed "
            "| ConvertTo-Json -Compress"
        )
        if not output:
            # 回退到 wmic
            output = _run(
                ["wmic", "nic", "get", "name,netenabled"],
                timeout=10,
            )
        # 跨语言检测：PowerShell 输出 Status 为 Up 或 Disabled 等英文值
        # wmic 输出 TRUE/FALSE
        if not output:
            item.status = "未检测到网络适配器信息"
            item.level = DiagnosisLevel.WARNING
        elif "Up" in output or "TRUE" in output or "True" in output:
            item.status = "正常运行"
            item.level = DiagnosisLevel.OK
            item.detail = "至少有一个网络适配器处于正常运作状态"
        else:
            item.status = "未检测到活动适配器"
            item.level = DiagnosisLevel.WARNING
            item.suggestion = "请检查网络硬件或驱动程序是否正常"
    except Exception as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_internet_connection() -> DiagnosisItem:
    """② 检测 Internet 连接（先 ping 公共 DNS，再尝试 HTTP 请求）"""
    item = DiagnosisItem(name="Internet 连接")
    try:
        # 方式一：ping 公共 DNS
        ping_out = _run(["ping", "-n", "2", "-w", "3000", "8.8.8.8"])
        if ping_out and "TTL=" in ping_out:
            item.status = "已连接"
            item.level = DiagnosisLevel.OK
            item.detail = "可访问 8.8.8.8"
            return item

        # 方式二：ping baidu.com（DNS 解析 + 连接）
        ping_out2 = _run(["ping", "-n", "2", "-w", "3000", "baidu.com"])
        if ping_out2 and "TTL=" in ping_out2:
            item.status = "已连接（DNS 解析正常）"
            item.level = DiagnosisLevel.OK
            item.detail = "可访问 baidu.com"
            return item

        # 方式三：尝试 socket 连接
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            item.status = "已连接（仅 IP 可达）"
            item.level = DiagnosisLevel.OK
            return item
        except OSError:
            pass

        item.status = "无法访问 Internet"
        item.level = DiagnosisLevel.WARNING
        item.suggestion = "请检查网络连接是否正常"
    except Exception as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_ip_address() -> DiagnosisItem:
    """③ 检测当前 IP 地址"""
    item = DiagnosisItem(name="IP 地址")
    try:
        # 获取所有非回环 IPv4 地址
        hostname = socket.gethostname()
        addrs = socket.getaddrinfo(hostname, None)
        real_ips = set()
        for addr in addrs:
            ip = addr[4][0]
            if not ip.startswith("127.") and ":" not in ip:  # 只取 IPv4
                real_ips.add(ip)
        if real_ips:
            ips_str = ", ".join(sorted(real_ips))
            item.status = ips_str
            item.level = DiagnosisLevel.OK
        else:
            # 尝试 ipconfig 获取
            ipcfg = _run(["ipconfig"], timeout=5)
            if "IPv4" in ipcfg:
                ips = re.findall(
                    r"IPv4[^\d]*(\d+\.\d+\.\d+\.\d+)", ipcfg
                )
                if ips:
                    item.status = ", ".join(ips)
                    item.level = DiagnosisLevel.OK
                else:
                    item.status = "未获取到有效 IP"
                    item.level = DiagnosisLevel.WARNING
            else:
                item.status = "未获取到有效 IP"
                item.level = DiagnosisLevel.WARNING
            item.suggestion = "尝试执行 ipconfig /renew 获取 IP"
    except Exception as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_gateway() -> DiagnosisItem:
    """④ 检测默认网关"""
    item = DiagnosisItem(name="默认网关")
    try:
        output = _run(["route", "print", "0.0.0.0"], timeout=5)
        if output:
            # 匹配网关 IP（route print 的第二行起有网关）
            gw_match = re.search(
                r"0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)",
                output,
            )
            if gw_match:
                gw = gw_match.group(1)
                item.status = gw
                item.level = DiagnosisLevel.OK
                # 验证网关是否可达
                ping_gw = _run(["ping", "-n", "1", "-w", "2000", gw])
                if ping_gw and "TTL=" in ping_gw:
                    item.detail = "网关可达"
                else:
                    item.detail = "网关已配置但不可达"
                return item
        item.status = "未发现默认网关"
        item.level = DiagnosisLevel.WARNING
        item.suggestion = "检查网络连接或路由表配置"
    except Exception as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_dns() -> DiagnosisItem:
    """⑤ 检测 DNS 服务器"""
    item = DiagnosisItem(name="DNS 服务器")
    try:
        # 从 ipconfig /all 获取 DNS
        ipcfg = _run(["ipconfig", "/all"], timeout=5)
        dns_servers = re.findall(
            r"DNS\s+服务器[.\s]*[:：]\s*(\d+\.\d+\.\d+\.\d+)",
            ipcfg,
        )
        if dns_servers:
            unique = list(dict.fromkeys(dns_servers))  # 去重保持顺序
            item.status = ", ".join(unique)
            # 验证 DNS 解析
            nslookup = _run(["nslookup", "baidu.com"], timeout=5)
            if nslookup and "Address" in nslookup and "Non-existent" not in nslookup:
                item.level = DiagnosisLevel.OK
                item.detail = "DNS 解析正常"
            else:
                item.level = DiagnosisLevel.WARNING
                item.detail = "DNS 已配置但解析异常"
                item.suggestion = "尝试执行 ipconfig /flushdns"
        else:
            item.status = "未配置 DNS"
            item.level = DiagnosisLevel.WARNING
            item.suggestion = "检查 DHCP 或手动配置 DNS"
    except Exception as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_dhcp() -> DiagnosisItem:
    """⑥ 检测 DHCP 状态"""
    item = DiagnosisItem(name="DHCP 状态")
    try:
        # 通过 PowerShell 获取 DHCP 启用状态（跨语言，返回 True/False）
        ps_out = _run_powershell(
            "Get-NetAdapter -Name * | Get-NetIPInterface -AddressFamily IPv4 "
            "| Select-Object Dhcp | ConvertTo-Json -Compress"
        )
        if ps_out and "True" in ps_out:
            item.status = "DHCP 已启用"
            item.level = DiagnosisLevel.OK
        elif ps_out and "False" in ps_out:
            item.status = "DHCP 已禁用（静态 IP）"
            item.level = DiagnosisLevel.INFO
            item.detail = "使用静态 IP 配置，DHCP 未启用"
        else:
            # 回退：从 ipconfig 判断（中/英文兼容）
            ipcfg = _run(["ipconfig", "/all"], timeout=5)
            dhcp_lines = [l for l in ipcfg.splitlines() if "DHCP" in l]
            if dhcp_lines:
                # 只要有一个适配器启用了 DHCP 就算启用
                any_enabled = any(
                    kw in l
                    for l in dhcp_lines
                    for kw in ("是", "Yes", "已启用", "Enabled", "enable")
                )
                any_disabled = any(
                    kw in l
                    for l in dhcp_lines
                    for kw in ("否", "No", "禁用", "Disabled", "disable")
                )
                if any_enabled:
                    item.status = "DHCP 已启用"
                    item.level = DiagnosisLevel.OK
                elif any_disabled:
                    item.status = "DHCP 已禁用（静态 IP）"
                    item.level = DiagnosisLevel.INFO
                    item.detail = "使用静态 IP 配置，DHCP 未启用"
                else:
                    item.status = "DHCP 状态不确定"
                    item.level = DiagnosisLevel.INFO
            else:
                item.status = "无法确定 DHCP 状态"
                item.level = DiagnosisLevel.INFO
    except Exception as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_system_proxy() -> DiagnosisItem:
    """⑦ 检测 Windows 系统代理（IE/Edge 代理设置）"""
    item = DiagnosisItem(name="系统代理")
    try:
        import winreg
        key_path = (
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ
        ) as key:
            proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
            if proxy_enable:
                proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
                item.status = f"已开启（{proxy_server}）"
                item.level = DiagnosisLevel.WARNING
                item.suggestion = (
                    "系统代理仍处于开启状态，可能是代理软件退出时未清理"
                )
            else:
                item.status = "未开启"
                item.level = DiagnosisLevel.OK
    except (ImportError, OSError) as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_winhttp_proxy() -> DiagnosisItem:
    """⑧ 检测 WinHTTP 代理"""
    item = DiagnosisItem(name="WinHTTP 代理")
    try:
        output = _run(
            ["netsh", "winhttp", "show", "proxy"], timeout=5
        )
        if output:
            output_lower = output.lower()
            # 跨语言检测：代理服务器行关键词
            proxy_keywords = [
                "proxy server",      # en
                "代理服务器",         # zh-CN
                "代理伺服器",         # zh-TW
                "プロキシ",           # ja
                "proxyserver",       # de
                "serveur proxy",     # fr
                "servidor proxy",    # es/pt
            ]
            has_proxy_line = any(kw in output_lower for kw in proxy_keywords)
            # "直接访问(无代理)" / "Directly access" / no proxy
            no_proxy_keywords = [
                "directly", "直接访问", "直接アクセス",
                "direct", "sin proxy", "kein proxy",
            ]
            is_direct = any(kw in output_lower for kw in no_proxy_keywords)

            if has_proxy_line and not is_direct:
                # 提取代理地址（REGEX 跨语言）
                match = re.search(
                    r"(?:Proxy Server|代理服务器|代理伺服器|プロキシ)[^:]*[:：]*\s*(.+)",
                    output,
                    re.IGNORECASE,
                )
                if match:
                    addr = match.group(1).strip()
                    if addr and addr not in ("（无）", "(none)", "なし"):
                        item.status = f"已配置（{addr}）"
                        item.level = DiagnosisLevel.WARNING
                        item.suggestion = "WinHTTP 代理残留，建议执行重置"
                        return item
        item.status = "未配置"
        item.level = DiagnosisLevel.OK
    except Exception as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_pac() -> DiagnosisItem:
    """⑨ 检测是否开启 PAC（自动配置脚本）"""
    item = DiagnosisItem(name="PAC 自动代理")
    try:
        import winreg
        key_path = (
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ
        ) as key:
            # 检查 AutoConfigUrl
            try:
                auto_url = winreg.QueryValueEx(
                    key, "AutoConfigURL"
                )[0]
            except FileNotFoundError:
                auto_url = ""

            if auto_url:
                item.status = f"已配置（{auto_url}）"
                item.level = DiagnosisLevel.WARNING
                item.suggestion = "PAC 代理脚本未清除，建议关闭"
            else:
                item.status = "未配置"
                item.level = DiagnosisLevel.OK
    except (ImportError, OSError) as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_localhost_proxy() -> DiagnosisItem:
    """⑩ 检测系统代理是否指向 127.0.0.1"""
    item = DiagnosisItem(name="本地代理检测")
    try:
        import winreg
        key_path = (
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ
        ) as key:
            proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
            if not proxy_enable:
                item.status = "未指向本地回环地址"
                item.level = DiagnosisLevel.OK
                return item

            proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
            loopback_patterns = (
                "127.0.0.1", "localhost", "127.0.0.1:",
            )
            if proxy_server and any(
                p in proxy_server for p in loopback_patterns
            ):
                item.status = f"代理指向本地 {proxy_server}"
                item.level = DiagnosisLevel.WARNING
                item.suggestion = (
                    "代理软件已退出但代理设置仍指向 127.0.0.1"
                )
            else:
                item.status = f"代理指向 {proxy_server}"
                item.level = DiagnosisLevel.INFO
    except (ImportError, OSError) as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_proxy_ports() -> DiagnosisItem:
    """⑪ 检测常见的代理端口是否被占用"""
    item = DiagnosisItem(name="代理端口检测")
    common_ports = [7890, 7897, 10808, 10809, 1080, 9090, 11434]
    occupied = []
    try:
        # 使用 netstat 检测端口
        netstat = _run(["netstat", "-ano"], timeout=5)
        if not netstat:
            # 回退到 PowerShell
            ps_out = _run_powershell(
                "Get-NetTCPConnection -State Listen "
                "| Select-Object LocalPort | ConvertTo-Json -Compress"
            )
            if ps_out:
                for port in common_ports:
                    if str(port) in ps_out:
                        occupied.append(str(port))
        else:
            for port in common_ports:
                # 匹配 LISTENING 状态的端口
                pattern = rf":{port}\s.*LISTENING"
                if re.search(pattern, netstat, re.IGNORECASE):
                    occupied.append(str(port))

        if occupied:
            item.status = f"正在监听：{', '.join(occupied)}"
            item.level = DiagnosisLevel.INFO
            item.detail = (
                "这些端口可能被代理软件占用，如已退出则属于残留"
            )
        else:
            item.status = "无常见代理端口占用"
            item.level = DiagnosisLevel.OK
    except Exception as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def _detect_virtual_adapter(keyword: str) -> str:
    """检测是否存在指定关键词的虚拟网卡（PowerShell）"""
    try:
        ps_out = _run_powershell(
            f"Get-NetAdapter -Name '*{keyword}*' "
            "| Select-Object Name, Status "
            "| ConvertTo-Json -Compress"
        )
        if ps_out and keyword in ps_out:
            # 提取名称
            name_match = re.search(r'"Name"\s*:\s*"([^"]+)"', ps_out)
            status_match = re.search(
                r'"Status"\s*:\s*"([^"]+)"', ps_out
            )
            name = name_match.group(1) if name_match else keyword
            status = (
                status_match.group(1)
                if status_match
                else "Unknown"
            )
            return f"{name}（{status}）"

        # 回退：从 ipconfig 中搜索
        ipcfg = _run(["ipconfig", "/all"], timeout=5)
        for line in ipcfg.splitlines():
            if keyword.lower() in line.lower():
                return "已检测到"
        return ""
    except Exception:
        return ""


def diagnose_wintun() -> DiagnosisItem:
    """⑫ 检测 Wintun 虚拟网卡"""
    item = DiagnosisItem(name="Wintun 虚拟网卡")
    result = _detect_virtual_adapter("Wintun")
    if result:
        item.status = result
        item.level = DiagnosisLevel.INFO
        item.detail = "Wintun 通常由 WireGuard/Clash 等软件创建"
    else:
        item.status = "未检测到"
        item.level = DiagnosisLevel.OK
    return item


def diagnose_wireguard_adapter() -> DiagnosisItem:
    """⑬ 检测 WireGuard 虚拟网卡"""
    item = DiagnosisItem(name="WireGuard 适配器")
    result = _detect_virtual_adapter("WireGuard")
    if result:
        item.status = result
        item.level = DiagnosisLevel.INFO
        item.detail = "WireGuard 适配器存在，如已卸载软件需手动清理"
    else:
        item.status = "未检测到"
        item.level = DiagnosisLevel.OK
    return item


def diagnose_tap_adapter() -> DiagnosisItem:
    """⑭ 检测 TAP 虚拟网卡（OpenVPN/TUN 等使用）"""
    item = DiagnosisItem(name="TAP 适配器")
    result = _detect_virtual_adapter("TAP")
    if not result:
        result = _detect_virtual_adapter("OpenVPN")
    if not result:
        # 检查通用 TAP-Windows
        ipcfg = _run(["ipconfig", "/all"], timeout=5)
        if "TAP" in ipcfg or "OpenVPN" in ipcfg:
            result = "已检测到 TAP 系列适配器"
    if result:
        item.status = result
        item.level = DiagnosisLevel.INFO
        item.detail = "TAP 适配器通常由 OpenVPN/TUN 等软件创建"
    else:
        item.status = "未检测到"
        item.level = DiagnosisLevel.OK
    return item


def diagnose_clash_adapter() -> DiagnosisItem:
    """⑮ 检测 Clash 虚拟网卡"""
    item = DiagnosisItem(name="Clash 虚拟网卡")
    result = _detect_virtual_adapter("Clash")
    if not result:
        # Clash Verge 可能使用不同的命名
        result = _detect_virtual_adapter("cfw")
    if result:
        item.status = result
        item.level = DiagnosisLevel.INFO
        item.detail = "Clash 适配器存在，如已卸载软件需手动清理"
    else:
        item.status = "未检测到"
        item.level = DiagnosisLevel.OK
    return item


def diagnose_winsock() -> DiagnosisItem:
    """⑯ 检测 Winsock 状态"""
    item = DiagnosisItem(name="Winsock 状态")
    try:
        output = _run(
            ["netsh", "winsock", "show", "state"], timeout=5
        )

        if output:
            output_lower = output.lower()
            # 跨语言检测：正常时的关键词（中/英/日/韩/德/法/西等）
            healthy_keywords = [
                "complete",     # en: The Winsock Catalog is complete
                "正常",          # zh-CN
                "正常です",      # ja
                "complet",      # fr: complet, it: completo
                "vollständig",  # de
                "completo",     # es, pt
            ]
            corrupt_keywords = [
                "corrupt",       # en: is corrupt / damaged
                "损坏",          # zh-CN
                "损坏",          # zh-TW
                "壊れ",          # ja
                "beschädigt",   # de
                "corrompu",     # fr
                "dañado",       # es
                "danneggiato",  # it
                "손상",          # ko
            ]
            if any(kw in output_lower for kw in healthy_keywords):
                item.status = "Winsock 正常"
                item.level = DiagnosisLevel.OK
            elif any(kw in output_lower for kw in corrupt_keywords):
                item.status = "Winsock 已损坏"
                item.level = DiagnosisLevel.WARNING
                item.suggestion = "建议执行 Winsock 重置"
            else:
                # 如果既找不到正常关键词也找不到损坏关键词，
                # 但 netsh 返回了输出，大概率是正常状态
                item.status = "Winsock 状态正常"
                item.level = DiagnosisLevel.OK
        else:
            item.status = "无法检测 Winsock 状态"
            item.level = DiagnosisLevel.INFO
    except Exception as e:
        item.status = "检测失败"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


def diagnose_hosts_file() -> DiagnosisItem:
    """⑰ 检测 Hosts 文件是否异常（仅提示，不修改）"""
    item = DiagnosisItem(name="Hosts 文件")
    hosts_path = (
        r"C:\Windows\System32\drivers\etc\hosts"
    )
    try:
        if not os.path.exists(hosts_path):
            item.status = "Hosts 文件不存在"
            item.level = DiagnosisLevel.INFO
            return item

        with open(hosts_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # 统计非空非注释行
        active_lines = [
            l.strip()
            for l in lines
            if l.strip() and not l.strip().startswith("#")
        ]

        # 检查常见异常条目
        suspicious = []
        for line in active_lines:
            parts = re.split(r"\s+", line)
            if len(parts) >= 2:
                ip, hostname = parts[0], parts[1]
                # 检查非回环 IP 映射了敏感域名
                if not ip.startswith("127.") and ip != "::1":
                    if any(
                        d in hostname.lower()
                        for d in [
                            "google", "facebook", "youtube",
                            "github", "microsoft", "apple",
                        ]
                    ):
                        suspicious.append(
                            f"{ip} → {hostname}"
                        )

        if suspicious:
            item.status = f"发现 {len(suspicious)} 条非默认映射"
            item.level = DiagnosisLevel.INFO
            item.detail = (
                "以下条目非 Windows 默认配置："
                + "; ".join(suspicious[:5])
            )
            if len(suspicious) > 5:
                item.detail += f" 及其他 {len(suspicious) - 5} 条"
        else:
            item.status = (
                f"正常（{len(active_lines)} 条非注释条目）"
            )
            item.level = DiagnosisLevel.OK
    except OSError as e:
        item.status = "无法读取"
        item.level = DiagnosisLevel.INFO
        item.detail = str(e)
    return item


# ====================================================================
# 诊断编排
# ====================================================================

_ALL_DIAGNOSE_FUNCTIONS = [
    ("网络适配器", diagnose_network_adapter),
    ("Internet 连接", diagnose_internet_connection),
    ("IP 地址", diagnose_ip_address),
    ("默认网关", diagnose_gateway),
    ("DNS 服务器", diagnose_dns),
    ("DHCP 状态", diagnose_dhcp),
    ("系统代理", diagnose_system_proxy),
    ("WinHTTP 代理", diagnose_winhttp_proxy),
    ("PAC 自动代理", diagnose_pac),
    ("本地回环代理", diagnose_localhost_proxy),
    ("代理端口占用", diagnose_proxy_ports),
    ("Wintun 网卡", diagnose_wintun),
    ("WireGuard 适配器", diagnose_wireguard_adapter),
    ("TAP 适配器", diagnose_tap_adapter),
    ("Clash 虚拟网卡", diagnose_clash_adapter),
    ("Winsock 状态", diagnose_winsock),
    ("Hosts 文件", diagnose_hosts_file),
]


def run_full_diagnosis() -> DiagnosisReport:
    """执行完整诊断，返回报告"""
    report = DiagnosisReport()
    report.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    items = []
    for name, func in _ALL_DIAGNOSE_FUNCTIONS:
        try:
            result = func()
            if not result.name:
                result.name = name
            items.append(result)
        except Exception as e:
            items.append(
                DiagnosisItem(
                    name=name,
                    status="检测异常",
                    level=DiagnosisLevel.INFO,
                    detail=str(e),
                )
            )

    report.items = items

    # ---- 分析整体健康状态 ----
    warnings = [i for i in items if i.level == DiagnosisLevel.WARNING]

    if not warnings:
        report.health_level = NetworkHealthLevel.HEALTHY
        report.conclusion = "网络配置完全正常。"
        report.recommendation = "无需修复，继续保持。"
    else:
        # 按异常类型分组，生成结论
        proxy_issues = [
            i for i in warnings
            if "代理" in i.name or "PAC" in i.name or "本地" in i.name
        ]
        winsock_issues = [
            i for i in warnings if "Winsock" in i.name
        ]
        connectivity_issues = [
            i for i in warnings
            if "连接" in i.name or "网关" in i.name
            or "IP" in i.name or "DNS" in i.name
        ]
        adapter_issues = [
            i for i in warnings if "适配器" in i.name
        ]

        # 判断严重程度
        if connectivity_issues or adapter_issues:
            report.health_level = NetworkHealthLevel.ERROR
        else:
            report.health_level = NetworkHealthLevel.WARNING

        # 生成结论
        conclusion_parts = []
        if proxy_issues:
            conclusion_parts.append(
                "检测到代理软件退出后遗留了系统代理配置。"
            )
        if winsock_issues:
            conclusion_parts.append("Winsock 状态异常。")
        if connectivity_issues:
            conclusion_parts.append("网络连接存在问题。")
        if adapter_issues:
            conclusion_parts.append("网络适配器存在异常。")

        report.conclusion = " ".join(conclusion_parts) if conclusion_parts else (
            f"检测到 {len(warnings)} 项配置异常。"
        )

        # 生成推荐修复方案
        if proxy_issues and not connectivity_issues:
            report.recommendation = "建议执行「一键修复」，将清理代理配置并刷新网络。"
        elif winsock_issues:
            report.recommendation = "建议先执行「一键修复」，如未解决请执行「高级修复」(Winsock 重置)。"
        elif connectivity_issues or adapter_issues:
            report.recommendation = "建议先执行「一键修复」，如未解决请重启电脑。"
        else:
            report.recommendation = "建议执行「一键修复」清理残留配置。"

    # 写入日志
    write_log(
        "诊断",
        "完成",
        (
            f"正常 {report.ok_count} 项, "
            f"异常 {report.warning_count} 项, "
            f"信息 {report.info_count} 项 | "
            f"健康状态: {report.health_level.value}"
        ),
    )

    return report


def quick_check_after_repair() -> DiagnosisReport:
    """修复后的快速验证检测（仅关键项：IP/网关/DNS/连接）"""
    report = DiagnosisReport()
    report.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    functions = [
        ("IP 地址", diagnose_ip_address),
        ("默认网关", diagnose_gateway),
        ("DNS 服务器", diagnose_dns),
        ("Internet 连接", diagnose_internet_connection),
    ]

    items = []
    for name, func in functions:
        try:
            result = func()
            if not result.name:
                result.name = name
            items.append(result)
        except Exception as e:
            items.append(
                DiagnosisItem(
                    name=name, status="检测失败",
                    level=DiagnosisLevel.INFO, detail=str(e),
                )
            )

    report.items = items
    warnings = [i for i in items if i.level == DiagnosisLevel.WARNING]

    if not warnings:
        report.health_level = NetworkHealthLevel.HEALTHY
        report.conclusion = "网络修复成功。"
        report.recommendation = "所有关键指标正常。"
    else:
        report.health_level = NetworkHealthLevel.ERROR
        report.conclusion = "部分异常仍存在，建议执行高级修复或重启电脑。"
        report.recommendation = "尝试以管理员权限运行高级修复。"
        write_log(
            "修复验证", "部分失败",
            f"{len(warnings)} 项关键检测未通过",
        )

    return report
