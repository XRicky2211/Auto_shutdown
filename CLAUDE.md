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
    ├── battery_monitor.py       # psutil 封装：读取电量百分比和电源状态
    ├── battery_analyzer.py      # 电量趋势分析：采样历史 → 放电速率 → 预估剩余时间
    ├── brightness_controller.py # 屏幕亮度读写（PowerShell WMI，零额外依赖）
    ├── config_manager.py        # JSON 配置读写（开发环境=项目目录，打包后=%APPDATA%）
    ├── holiday_api.py           # 中国节假日数据获取（timor.tech API + 本地 JSON 缓存）
    └── game_detector.py         # 检测前台窗口是否为全屏程序（Win32 API）
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

**亮度自动调节**（`core/brightness_controller.py` + `ui/widgets_dialog.py` + `ui/brightness_settings_dialog.py`）：
- 通过 PowerShell WMI（`WmiMonitorBrightness` / `WmiMonitorBrightnessMethods`）读写笔记本内置屏幕亮度，**零额外依赖**
- 程序启动时根据当前电源状态自动设置一次亮度；运行期间检测到 AC 插拔自动切换
- 两组亮度值可独立配置：AC 电源（默认 100%）、电池供电（默认 50%）
- 交互路径：主窗口「小组件」按钮 → 小组件弹窗（功能清单） → 亮度控制卡片「设置」→ 子弹窗（滑块 + 启用开关）
- 小组件弹窗为可扩展框架，未来可在其中追加更多小功能区卡片
- 仅支持笔记本内置屏幕，外接显示器（HDMI/DP）不生效

### PyInstaller 打包注意事项

- `build_exe.py` 会清理 build/dist 目录、重装依赖、调用 `AutoShutdownHelper.spec` 打包
- 打包后 exe 依赖 `sys.frozen` 判断路径（`config_manager.py`），无需额外配置
