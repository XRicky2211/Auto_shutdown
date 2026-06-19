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

# 打包为单文件 exe
python build_exe.py

# 清理 build/dist 后直接通过 spec 打包（build_exe.py 因权限失败时备用）
python -m PyInstaller AutoShutdownHelper.spec
```

## 架构概览

**Windows 专用**桌面应用，技术栈：Python 3.9+ / PySide6 / psutil。常驻系统托盘，最小化到托盘而非退出。

### 分层结构

```text
main.py                 # 入口：单实例保护 → 创建 MainWindow → 事件循环
├── ui/                 # PySide6 GUI 层
│   ├── main_window.py        # 主窗口 + 旧引擎倒计时 + 低电量检测
│   ├── email_settings_dialog.py # 邮件 SMTP 配置弹窗
│   └── *_dialog.py           # 各功能设置弹窗（纯 UI，无业务逻辑）
└── core/               # 业务逻辑层（不依赖 Qt，可独立测试）
    ├── countdown_manager.py   # 倒计时管理器：end_time 唯一真相源，7 个 Qt 信号
    ├── task_executor.py       # 统一任务执行入口（is_shutting_down 防重复）
    ├── notification/          # 邮件通知模块
    │   └── email_sender.py    # EmailSender：SMTP SSL 发送 + 幂等 task_id 去重
    ├── battery_monitor.py     # psutil 封装：电量百分比和电源状态
    ├── battery_analyzer.py    # 放电速率分析 + 剩余时间预估
    ├── brightness_controller.py # PowerShell WMI 读写屏幕亮度
    ├── config_manager.py      # JSON 配置（开发目录 / %APPDATA%）
    ├── holiday_api.py         # 中国节假日数据（timor.tech API + JSON 缓存）
    └── game_detector.py       # Win32 检测前台窗口是否全屏
```

### 新旧引擎架构（`_use_new_engine`）

项目正在进行增量重构：将倒计时状态机从 `MainWindow` 迁移到 `CountdownManager`，任务执行从 `subprocess.Popen` 迁移到 `TaskExecutor`。

```text
新引擎（_use_new_engine=True，当前默认）：
  CountdownManager._on_tick() ← QTimer(Qt.PreciseTimer)
    ├─ end_time 实时计算 remaining（不累加，消除累积误差）
    ├─ 7 个 Qt 信号驱动 MainWindow UI 更新
    └─ task_due → TaskExecutor.execute() 统一执行

旧引擎（_use_new_engine=False）：
  MainWindow._on_tick() ← QTimer
    ├─ 自维护 remaining_seconds, end_time, fired_reminders
    └─ subprocess.Popen(TASK_COMMANDS) 直接执行
```

新引擎通过这 7 个信号与 UI 通信：

| 信号 | MainWindow 回调 | 作用 |
| - | - | - |
| `time_updated(int)` | `_on_countdown_time_updated` | UI 刷新剩余时间 |
| `reminder_needed(int)` | `_show_reminder` | 弹提醒窗 |
| `task_due(str)` | `_on_task_due` | 到点执行 |
| `game_end_warning(str,int)` | `_on_game_end_warning` | 游戏结束警告 |
| `state_changed(bool)` | `_on_countdown_state_changed` | 按钮文字切换 |
| `countdown_cancelled()` | `_on_countdown_cancelled` | UI 重置 |
| `countdown_started()` | `_on_countdown_started` | 节假日标签更新 |

### 核心设计决策

**end_time 时间戳驱动**：CountdownManager 以 `QDateTime end_time` 为唯一真相源。`remaining_seconds` 通过 `secsTo()` 实时计算，永不手动加减。`QTimer` 仅驱动检查，不是计时工具。这消除了睡眠唤醒后的累积误差。

**唤醒补偿**：`CountdownManager.check_due()` 是外部唤醒检测入口。系统从睡眠/休眠恢复后由 `MainWindow.changeEvent()` 调用。如果 end_time 已过，立即触发 `task_due`。`load_state()` 恢复时发现已过期则延迟一帧触发执行。

**任务执行**（`core/task_executor.py`）：`execute(task_type)` 统一入口，`is_shutting_down` 防重复。关机/重启加 `/f` 避免 Windows 弹窗。睡眠使用 Win32 `SetSuspendState(False, False, False)`。

**低电量两级阈值**（`main_window.py: _check_battery()`）：

- warning（默认 20%）：橙色弹窗，"我知道了/立即关机/本次禁用"
- critical（默认 10%）：红色弹窗 + 60s 自动关机倒计时
- 频率自适应：正常 180s → 接近警告 30s → 临界 10s

**游戏模式**：Win32 `GetForegroundWindow` + `GetWindowRect` 检测前台窗口面积 ≥ 屏幕 95%。到 0 时全屏 → 自动推迟 15 分钟；全屏退出 → game_end_countdown 秒警告期 → 执行。

### 弹窗层次

所有弹窗 via `dialog.exec()`，主窗口 Accept 后读取 getter：

- **TimerSettingsDialog** — 倒计时/预约模式 + 5 种任务类型
- **ReminderSettingsDialog** — 多级提醒 + 推迟分钟数
- **SchedulePlanDialog** — 计划类型（仅一次/每天/工作日/周末/每周）
- **HolidaySettingsDialog** — 节假日跳过 + 上下个节假日查看
- **GameModeSettingsDialog** — 启用 + 游戏结束后倒计时秒数
- **BatterySettingsDialog** — 两级阈值（warning/critical 联动）
- **LowBatteryDialog** — 低电量弹窗，critical 含 60s 自动关机
- **ReminderDialog** — 取消/推迟/确认预约，实时时间刷新
- **WidgetsDialog → BrightnessSettingsDialog** — 嵌套子弹窗

### Git 远程配置

使用 SSH 协议推送（已配置，无需额外操作）：

```bash
# 远程地址：git@github.com:XRicky2211/Auto_shutdown.git
git remote -v                    # 查看当前远程
git push origin master           # 推送至 GitHub
```

### 注意事项

- **仅支持 Windows**（Win32 API、注册表、PowerShell WMI）
- 无测试套件，无日志系统
- `settings.json` 开发/打包路径不同
- `TASK_COMMANDS` 在 `main_window.py` 和 `task_executor.py` 各有一份——新引擎只用后者。`_execute_task()` 和 `_execute_shutdown()` 在新引擎下是空函数
- 打包约 45 MB（PySide6），build/dist 被锁时先 `taskkill /F /IM AutoShutdownHelper.exe`
- 亮度仅笔记本内置屏幕生效，外接显示器不生效
