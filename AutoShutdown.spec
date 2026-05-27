# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

sys.setrecursionlimit(5000)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PySide6.QtNetwork',
        'PySide6.QtGui',
        'PySide6.QtCore',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'numpy',
        'PIL',
        'pandas',
        'cv2',
        'notebook',
        'jupyter',
        'setuptools',
        'pip',
        'pkg_resources',
    ],
    noarchive=False,
)

# 确保 Qt 插件和平台 DLL 被正确打包
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AutoShutdown',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 无控制台窗口 (GUI 模式)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 可指定图标: icon='assets/icon.ico'
)
