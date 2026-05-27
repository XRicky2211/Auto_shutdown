# 自动关机助手 (Auto Shutdown)

[![GitHub release](https://img.shields.io/github/v/release/XRicky2211/Auto_shutdown)](https://github.com/XRicky2211/Auto_shutdown/releases)
[![Python](https://img.shields.io/badge/Python-3.9+-blue)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.10-green)](https://pypi.org/project/PySide6/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)](https://github.com/XRicky2211/Auto_shutdown)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

一款功能强大的 Windows 定时关机工具，支持定时关机、重启、注销、睡眠、休眠等多种任务类型，提供低电量自动关机、节假日跳过、游戏模式等人性化功能。

---

## 功能特性

### 核心功能

| 功能 | 说明 |
|------|------|
| **定时关机 / 重启 / 注销 / 睡眠 / 休眠** | 五种任务类型，满足不同场景需求 |
| **倒计时模式** | 设置 N 分钟后执行任务 |
| **预约模式** | 支持仅一次 / 每天 / 工作日 / 周末 / 每周定时 |
| **多级提醒** | 任务执行前 1 分钟、30 分钟等，可自定义提醒时间 |
| **推迟执行** | 收到提醒后可选择推迟执行（自定义分钟数） |

### 特色功能

| 功能 | 说明 |
|------|------|
| **低电量自动关机** | 电池电量低于设定阈值时自动关机，避免数据丢失 |
| **节假日自动跳过** | 自动识别中国法定节假日，节假日不执行定时任务 |
| **游戏模式** | 检测到全屏游戏时自动推迟任务，游戏结束后才执行 |
| **系统托盘** | 最小化到系统托盘，后台静默运行 |
| **开机自启** | 通过注册表设置开机自启动 |

### 技术特性

| 特性 | 说明 |
|------|------|
| **睡眠安全** | 通过 Windows API 阻止系统睡眠，确保定时任务可靠执行 |
| **任务计划程序** | 使用 Windows 任务计划程序 (schtasks) 替代 shutdown /t，支持从睡眠中唤醒执行 |
| **单实例保护** | 通过 IPC 本地 Socket 确保只运行一个实例 |
| **配置持久化** | 所有设置自动保存至 JSON 文件，下次启动自动恢复 |
| **窗口记忆** | 自动记忆窗口位置和大小 |
| **唤醒定时器** | 自动启用系统唤醒定时器，保障低电量巡检任务在睡眠时也能执行 |

---

## 截图

> TODO: 添加程序截图

---

## 快速开始

### 方式一：下载预编译版本（推荐）

1. 前往 [Releases](https://github.com/XRicky2211/Auto_shutdown/releases) 页面
2. 下载最新版本的 `AutoShutdown.exe`
3. 双击运行即可

### 方式二：从源码运行

```bash
# 克隆仓库
git clone https://github.com/XRicky2211/Auto_shutdown.git
cd Auto_shutdown

# 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行程序
python main.py
```

### 方式三：打包为可执行文件

```bash
pip install pyinstaller
pyinstaller AutoShutdown.spec
# 或
pyinstaller --onefile --windowed --name AutoShutdown main.py
```

生成的可执行文件在 `dist/AutoShutdown.exe`。

---

## 使用说明

1. **启动程序** — 运行后程序图标出现在系统托盘
2. **设置定时** — 点击「定时设置」选择模式和任务类型
   - 倒计时模式：输入分钟数
   - 预约模式：选择计划类型（每天/工作日/每周等）和具体时间
3. **设置提醒** — 点击「提醒设置」自定义提醒时间和推迟时长
4. **开始任务** — 点击「启动定时关机」按钮开始倒计时
5. **低电量设置** — 点击「低电量设置」配置电量阈值（默认 15%）
6. **游戏模式** — 点击「游戏模式」开启，全屏程序运行时自动推迟任务
7. **节假日跳过** — 点击「节假日跳过」配置是否跳过中国法定节假日

程序关闭时自动隐藏到系统托盘，不会退出。右键托盘图标可快速操作。

---

## 项目结构

```
Auto_shutdown/
├── main.py                          # 程序入口，单实例保护与应用启动
├── core/
│   ├── battery_monitor.py           # 电池状态检测
│   ├── config_manager.py            # 配置持久化（JSON 读写）
│   ├── game_detector.py             # 全屏程序（游戏）检测
│   ├── holiday_api.py               # 中国节假日 API 接口
│   ├── power_manager.py             # Windows 电源管理（阻止/允许睡眠）
│   └── task_scheduler.py            # Windows 任务计划程序集成
├── ui/
│   ├── main_window.py               # 主窗口（卡片式 UI）
│   ├── battery_settings_dialog.py   # 低电量设置弹窗
│   ├── game_mode_settings_dialog.py # 游戏模式设置弹窗
│   ├── holiday_settings_dialog.py   # 节假日跳过设置弹窗
│   ├── reminder_dialog.py           # 关机前提醒弹窗
│   ├── reminder_settings_dialog.py  # 提醒设置弹窗
│   ├── schedule_plan_dialog.py      # 预约计划设置弹窗
│   └── timer_settings_dialog.py     # 定时设置弹窗
└── requirements.txt                 # Python 依赖
```

---

## 依赖

- [Python](https://www.python.org/) 3.9+
- [PySide6](https://pypi.org/project/PySide6/) 6.10+ — Qt 桌面 UI 框架
- Windows 操作系统（使用了 Windows 特有的 API）

---

## 常见问题

**Q：为什么使用任务计划程序而不是 shutdown /t？**
A：`shutdown /t` 在系统睡眠时不会执行，且会弹出系统通知窗口。任务计划程序支持 `/WAKE` 参数，可从睡眠中唤醒系统执行任务，且静默运行无弹窗。

**Q：低电量关机在睡眠时能生效吗？**
A：可以。程序创建了一个独立于 Python 进程的 Windows 计划任务，每 5 分钟巡检一次电池电量，即使系统睡眠也能唤醒执行。

**Q：游戏模式如何工作？**
A：游戏模式会检测前台是否正在运行全屏程序（游戏）。如果到点检测到游戏正在运行，任务会自动推迟 15 分钟；游戏结束后再给你一个倒计时缓冲期。

---

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。

---

## 致谢

- 节假日数据来源：[NateScarlet/holiday-cn](https://github.com/NateScarlet/holiday-cn)
- UI 设计：PySide6 (Qt for Python)
