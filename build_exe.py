"""
打包脚本 —— 运行此脚本即可重新生成 exe 文件
用法：python build_exe.py
"""

import os
import sys
import shutil
import subprocess


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(root, "AutoShutdownHelper.spec")
    dist_dir = os.path.join(root, "dist")
    build_dir = os.path.join(root, "build")

    # 清理上一次打包的临时文件，确保全新构建
    print("正在清理旧的打包文件...")
    for d in (build_dir, dist_dir):
        if os.path.isdir(d):
            shutil.rmtree(d)
            print(f"  已删除 {d}")

    # 确保依赖已安装
    print("正在检查依赖...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r",
         os.path.join(root, "requirements.txt")],
    )

    # 执行 PyInstaller 打包
    print("正在打包 exe，请稍候...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", spec_file],
        cwd=root,
    )

    if result.returncode != 0:
        print("打包失败，请检查上方错误信息。")
        sys.exit(1)

    # 找生成的 exe
    exe_name = "AutoShutdownHelper.exe"
    exe_path = os.path.join(dist_dir, exe_name)
    if os.path.isfile(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"\n打包成功！exe 路径：{exe_path}")
        print(f"文件大小：{size_mb:.1f} MB")
    else:
        print(f"\n打包完成，但未找到 {exe_name}，请检查 dist 目录。")
        sys.exit(1)


if __name__ == "__main__":
    main()
