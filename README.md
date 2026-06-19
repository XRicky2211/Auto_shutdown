# 自动关机助手 (Auto Shutdown Helper)

Windows 桌面定时关机工具，支持多种任务类型、低电量保护、节假日跳过、游戏模式、亮度自动调节等实用功能。

## 功能概览

| 功能 | 说明 |
|------|------|
| ⏱ 定时任务 | 倒计时 / 预约模式（每日/工作日/周末/每周），支持关机/重启/注销/睡眠/休眠 |
| 🔔 多级提醒 | 可配置多个提前提醒时间 + 推迟执行 |
| 🔋 低电量保护 | 两级阈值策略（警告 + 临界），检测频率自适应，防止电池过放 |
| 📅 节假日跳过 | 接入中国节假日 API，节假日自动跳过关机 |
| 🎮 游戏模式 | 检测全屏程序运行中自动推迟任务，游戏结束后倒计时执行 |
| ☀ 亮度自动调节 | 根据电源状态（AC/电池）自动切换屏幕亮度，保护视力延长续航 |
| 📧 邮件通知 | SMTP SSL 发送关机/重启/注销通知，支持多条触发原因区分、发送确认后执行任务 |
| 🖥 系统托盘 | 关闭窗口最小化到托盘，右键菜单快速操作，支持开机自启 |

## 系统要求

- Windows 10 / 11 (64-bit)
- 无需管理员权限（开机自启功能除外）
- 笔记本用户可体验全部功能（电池检测 + 亮度调节），台式机也可正常使用核心功能

## 快速开始

### 开发运行

```bash
# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 启动
python main.py
```

### 打包为 exe

```bash
python build_exe.py
```

输出文件在 `dist/AutoShutdownHelper.exe`，约 45 MB。

## 项目结构

```text
main.py                    # 入口：单实例保护 → 创建 MainWindow
├── ui/                    # PySide6 GUI 层
│   ├── main_window.py     # 主窗口（卡片式布局）
│   ├── email_settings_dialog.py # 邮件 SMTP 配置弹窗
│   └── *_dialog.py        # 各功能设置弹窗
└── core/                  # 业务逻辑层（不依赖 Qt）
    ├── countdown_manager.py     # 倒计时管理器
    ├── task_executor.py         # 统一任务执行入口
    ├── notification/            # 邮件通知模块
    │   └── email_sender.py      # SMTP SSL 发送 + 幂等去重
    ├── battery_monitor.py       # psutil 电池状态
    ├── battery_analyzer.py      # 放电趋势分析
    ├── brightness_controller.py # WMI 屏幕亮度控制
    ├── config_manager.py        # JSON 配置持久化
    ├── holiday_api.py           # 中国节假日 API
    └── game_detector.py         # Win32 全屏检测
```

## 技术栈

- **Python 3.9+** / **PySide6** / **psutil**
- 亮度控制通过 PowerShell WMI，不依赖第三方库
- 打包工具 PyInstaller，单文件 exe

## 配置存储

开发环境：项目根目录 `settings.json`
打包后：`%APPDATA%/AutoShutdownHelper/settings.json`
