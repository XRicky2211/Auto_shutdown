"""
打包脚本 —— 运行 python build_exe.py 即可生成 exe 文件
特点：实时显示进度条和耗时统计
"""

import os
import sys
import shutil
import subprocess
import time
import re


# ======================== 进度条 ========================

# PyInstaller 输出中的关键阶段标志 → 进度百分比
_STAGE_PATTERNS = [
    (r"checking Analysis",           3),
    (r"Building because",            8),
    (r"Looking for Python shared",  12),
    (r"Using Python shared",        16),
    (r"Running Analysis",           20),
    (r"Analyzing modules",          25),
    (r"Processing module",          50),   # 模块处理阶段范围广
    (r"building (base_library|lib)", 55),  # base_library.zip 等
    (r"Looking for ctypes depend",   60),
    (r"Performing binary vs. data",  65),
    (r"Building COLLECT",            70),
    (r"Building PYZ",               75),
    (r"Building PKG",               82),
    (r"Building EXE",               90),
    (r"Building BOOTLOADER",         92),
    (r"Completed, returning",        98),
    (r"successfully",              100),
]

# 一些阶段在进度条中段反复出现，用特殊规则平滑过渡
_LAST_PROGRESS = 0


def estimate_progress(line: str) -> int:
    """根据 PyInstaller 输出行估算进度百分比（0-100）"""
    global _LAST_PROGRESS

    # 先看是否匹配已知阶段
    best = 0
    for pattern, pct in _STAGE_PATTERNS:
        if re.search(pattern, line):
            best = max(best, pct)
            break

    # "Processing module" 每出现一次，在 25-55 之间微增
    if re.search(r"Processing module", line):
        # 用已读行数估算，但不超过本阶段上限
        best = max(30, min(55, _LAST_PROGRESS + 1))

    if best > 0:
        _LAST_PROGRESS = best
    return _LAST_PROGRESS


def draw_bar(pct: int, elapsed: float, label: str = ""):
    """画控制台进度条（纯 ASCII，兼容 GBK 编码）"""
    bar_w = 40
    filled = int(bar_w * pct / 100)
    bar = "#" * filled + "." * (bar_w - filled)
    sys.stdout.write(f"\r  [{bar}] {pct:3d}%  {elapsed:4.0f}s  {label}")
    sys.stdout.flush()


# ======================== 主流程 ========================


def main():
    global _LAST_PROGRESS
    root = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(root, "AutoShutdownHelper.spec")
    dist_dir = os.path.join(root, "dist")
    build_dir = os.path.join(root, "build")
    exe_name = "AutoShutdownHelper.exe"
    exe_path = os.path.join(dist_dir, exe_name)

    start_time = time.time()

    # ====== 第一步：清理 ======
    print("[1/2] 清理旧打包文件...")
    for d in (build_dir, dist_dir):
        if os.path.isdir(d):
            shutil.rmtree(d)
            print(f"  [OK] 已删除 {d}")

    # ====== 第二步：打包 ======
    print(f"\n[2/2] 开始打包（PyInstaller）\n")

    # 使用 --noconfirm 避免删除确认交互
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", spec_file]

    proc = subprocess.Popen(
        cmd,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,     # 行缓冲，实时读取
    )

    _LAST_PROGRESS = 0

    # 逐行读取输出，更新进度条
    for raw_line in proc.stdout:
        line = raw_line.rstrip()
        if not line:
            continue

        pct = estimate_progress(line)
        elapsed = time.time() - start_time

        # 取最后一段有用信息作为标签（去掉 "INFO: " 前缀）
        label = re.sub(r"^\d+ INFO: ", "", line)
        if len(label) > 50:
            label = label[:47] + "..."

        draw_bar(pct, elapsed, label)

    proc.wait()
    elapsed = time.time() - start_time
    print()  # 换行

    # ====== 结果 ======
    if proc.returncode != 0:
        print(f"\n[FAIL] 打包失败（退出码 {proc.returncode}），耗时 {elapsed:.0f} 秒")
        print(f"  查看上方错误信息。常见原因：")
        print(f"    1. 被安全软件拦截 -> 暂时关闭后再试")
        print(f"    2. 磁盘空间不足 -> 检查 C 盘剩余空间")
        print(f"    3. 虚拟环境未激活 -> 先运行 .venv\\Scripts\\activate")
        sys.exit(1)

    if os.path.isfile(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"\n[OK] 打包成功！耗时 {elapsed:.0f} 秒")
        print(f"  路径：{exe_path}")
        print(f"  大小：{size_mb:.1f} MB")
    else:
        print(f"\n[FAIL] 打包完成但未找到 {exe_name}")
        print(f"  请检查 {dist_dir} 目录")
        sys.exit(1)


if __name__ == "__main__":
    main()
