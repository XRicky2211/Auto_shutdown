# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 构建/运行命令

```bash
# 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 开发运行
python main.py

# 打包为单文件 exe（通过 build_exe.py 脚本）
python build_exe.py

# 或手动使用 PyInstaller（首次自动生成 spec，后续使用 spec 打包）
pyinstaller --onefile --windowed --name AutoShutdownHelper main.py
pyinstaller AutoShutdownHelper.spec
```

## 架构概览

**Windows 专用**桌面应用，技术栈：Python 3.9+ / PySide6 / psutil。程序启动后常驻系统托盘，最小化到托盘而非退出。

### 分层结构

```
main.py                 # 入口：单实例保护 → 创建 MainWindow → 进入事件循环
├── ui/                 # PySide6 GUI 层
│   ├── main_window.py  # 主窗口：卡片式布局，包含倒计时、电量进度条、所有设置入口
│   └── *_dialog.py     # 各功能设置弹窗
└── core/               # 业务逻辑层（不依赖 Qt，可独立测试）
    ├── battery_monitor.py    # psutil 封装：读取电量百分比和电源状态
    ├── battery_analyzer.py   # 电量趋势分析：采样历史 → 放电速率 → 预估剩余时间
    ├── config_manager.py     # JSON 配置读写（开发环境=项目目录，打包后=%APPDATA%）
    ├── holiday_api.py        # 中国节假日数据获取（timor.tech API + 本地 JSON 缓存）
    └── game_detector.py      # 检测前台窗口是否为全屏程序（Win32 API）
```

### 核心设计决策

**关机通过 subprocess 执行系统命令**（`ui/main_window.py` → `TASK_COMMANDS` 字典）：
- 关机: `shutdown /s /t 0`
- 重启: `shutdown /r /t 0`
- 注销: `shutdown /l`
- 睡眠: `rundll32.exe powrprof.dll,SetSuspendState 0,0,0`
- 休眠: `shutdown /h`

**单实例保护**（`main.py`）：`QSharedMemory` 检测已有实例 + `QLocalServer`/`QLocalSocket` IPC 通知已有实例显示窗口

**配置持久化**（`config_manager.py`）：开发环境读写项目根目录 `settings.json`；打包后在 `%APPDATA%/AutoShutdownHelper/settings.json`

**低电量采用两级阈值策略**（`ui/main_window.py`）：
- `warning_threshold`：弹出提醒，用户可选择"我知道了"、"推迟"或"立即关机"
- `critical_threshold`：弹出紧急弹窗，选项更激进
- 检测频率自适应：正常 180s → 接近警告 30s → 临界 10s

### PyInstaller 打包注意事项

- `build_exe.py` 会清理 build/dist 目录、重装依赖、调用 `AutoShutdownHelper.spec` 打包
- 打包后 exe 依赖 `sys.frozen` 判断路径（`config_manager.py`），无需额外配置
