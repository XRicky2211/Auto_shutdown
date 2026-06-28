# --------------------------------------------------------------------------
# 文件：ui/network_repair_dialog.py
# 用途：网络诊断与修复弹窗——诊断检测 / 一键修复 / 高级修复 UI
# 说明：完全遵循项目现有 UI 风格；使用 threading + Signal 异步执行
# --------------------------------------------------------------------------

from typing import Optional
import threading

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QWidget,
    QGraphicsDropShadowEffect, QProgressBar, QTextEdit,
    QMessageBox, QFileDialog, QApplication,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QClipboard

from core.network_repair import (
    run_full_diagnosis,
    quick_check_after_repair,
    RepairService,
    ELEVATION_REQUIRED,
    DiagnosisReport,
    DiagnosisLevel,
    NetworkHealthLevel,
    RepairProgress,
    export_logs,
    write_log,
)

# ---- 状态常量 ----
_STATE_IDLE = 0
_STATE_DIAGNOSING = 1
_STATE_DIAGNOSIS_DONE = 2
_STATE_REPAIRING = 3
_STATE_REPAIR_DONE = 4


class NetworkRepairDialog(QDialog):
    """网络诊断与修复弹窗

    异步执行的信号定义：
        _diagnosis_finished: 诊断完成时发送完整报告
        _repair_progress:    修复进度更新
        _repair_finished:    修复完成时 (success, report)
        _quick_check_finished: 修复后快速检测报告
    """

    _diagnosis_finished = Signal(object)    # DiagnosisReport
    _repair_progress = Signal(object)       # RepairProgress
    _repair_finished = Signal(object, object)  # (bool, DiagnosisReport)
    _quick_check_finished = Signal(object)  # DiagnosisReport

    def __init__(self, parent=None):
        """初始化弹窗：设置 UI、信号绑定、初始状态"""
        super().__init__(parent)
        self.setWindowTitle("网络诊断与修复")
        self.setMinimumSize(560, 640)

        # ---- 内部状态 ----
        self._state = _STATE_IDLE
        self._report: Optional[DiagnosisReport] = None
        self._repair_service = RepairService()

        # ---- 信号连接 ----
        self._diagnosis_finished.connect(self._on_diagnosis_finished)
        self._repair_progress.connect(self._on_repair_progress)
        self._repair_finished.connect(self._on_repair_finished)
        self._quick_check_finished.connect(self._on_quick_check_finished)

        self._setup_ui()
        self._update_ui_for_state()

    # ====================================================================
    # 界面构建
    # ====================================================================

    def _setup_ui(self):
        """构建完整界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ── 标题 ──
        title = QLabel("网络诊断与修复")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #339AF0;
            padding-bottom: 4px;
        """)
        layout.addWidget(title)

        # ── 顶部：健康状态卡片 ──
        self._health_card = QFrame()
        self._health_card.setObjectName("healthCard")
        self._health_card.setMinimumHeight(56)
        self._health_card.setStyleSheet("""
            QFrame#healthCard {
                background-color: #EBFBEE;
                border: 1px solid #B2F2BB;
                border-radius: 10px;
            }
        """)
        health_layout = QHBoxLayout(self._health_card)
        health_layout.setContentsMargins(18, 12, 18, 12)

        self._health_icon = QLabel("🟢")
        self._health_icon.setStyleSheet("font-size: 22px; border: none;")
        health_layout.addWidget(self._health_icon)

        self._health_text = QLabel("点击「开始智能检测」检查网络状态")
        self._health_text.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #2B8A3E; border: none;"
        )
        health_layout.addWidget(self._health_text, 1)

        # 阴影
        health_shadow = QGraphicsDropShadowEffect()
        health_shadow.setBlurRadius(16)
        health_shadow.setColor(QColor(0, 0, 0, 12))
        health_shadow.setOffset(0, 2)
        self._health_card.setGraphicsEffect(health_shadow)

        layout.addWidget(self._health_card)

        # ── 诊断列表（滚动区域） ──
        diag_label = QLabel("诊断结果")
        diag_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #495057; padding-top: 2px;"
        )
        layout.addWidget(diag_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #F1F3F5;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #CED4DA;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self._diag_container = QWidget()
        self._diag_container.setStyleSheet("background: transparent;")
        self._diag_layout = QVBoxLayout(self._diag_container)
        self._diag_layout.setContentsMargins(0, 0, 0, 0)
        self._diag_layout.setSpacing(4)

        # 占位提示（无诊断数据时显示）
        self._diag_placeholder = QLabel("尚未检测，请点击「开始智能检测」")
        self._diag_placeholder.setAlignment(Qt.AlignCenter)
        self._diag_placeholder.setStyleSheet(
            "color: #ADB5BD; font-size: 13px; padding: 24px 0; background: transparent;"
        )
        self._diag_layout.addWidget(self._diag_placeholder)

        self._diag_layout.addStretch()
        scroll.setWidget(self._diag_container)
        layout.addWidget(scroll, 1)

        # ── 结论与建议区域 ──
        self._conclusion_card = QFrame()
        self._conclusion_card.setObjectName("conclusionCard")
        self._conclusion_card.setStyleSheet("""
            QFrame#conclusionCard {
                background-color: #FFF9DB;
                border: 1px solid #FFEC99;
                border-radius: 8px;
            }
        """)
        conclusion_layout = QVBoxLayout(self._conclusion_card)
        conclusion_layout.setContentsMargins(14, 10, 14, 10)
        conclusion_layout.setSpacing(4)

        self._conclusion_label = QLabel("结论：—")
        self._conclusion_label.setWordWrap(True)
        self._conclusion_label.setStyleSheet(
            "font-size: 12px; color: #495057; border: none;"
        )

        self._recommend_label = QLabel("建议：—")
        self._recommend_label.setWordWrap(True)
        self._recommend_label.setStyleSheet(
            "font-size: 12px; color: #E67700; font-weight: bold; border: none;"
        )

        conclusion_layout.addWidget(self._conclusion_label)
        conclusion_layout.addWidget(self._recommend_label)
        self._conclusion_card.setVisible(False)
        layout.addWidget(self._conclusion_card)

        # ── 修复进度区域（默认隐藏） ──
        self._progress_card = QFrame()
        self._progress_card.setObjectName("progressCard")
        self._progress_card.setStyleSheet("""
            QFrame#progressCard {
                background-color: #F0F7FF;
                border: 1px solid #D0E8FF;
                border-radius: 8px;
            }
        """)
        progress_layout = QVBoxLayout(self._progress_card)
        progress_layout.setContentsMargins(14, 10, 14, 10)
        progress_layout.setSpacing(6)

        # 当前步骤文字
        self._step_label = QLabel("准备中...")
        self._step_label.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #1971C2; border: none;"
        )
        progress_layout.addWidget(self._step_label)

        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedHeight(18)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #D0E8FF;
                border-radius: 8px;
                background-color: #E9F3FF;
                text-align: center;
                font-size: 11px;
                color: #1971C2;
            }
            QProgressBar::chunk {
                background-color: #339AF0;
                border-radius: 7px;
            }
        """)
        progress_layout.addWidget(self._progress_bar)

        # 执行日志（只读文字框）
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(80)
        self._log_text.setStyleSheet("""
            QTextEdit {
                background: #F8F9FA;
                border: 1px solid #DDE3E9;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 11px;
                color: #495057;
            }
        """)
        progress_layout.addWidget(self._log_text)

        self._progress_card.setVisible(False)
        layout.addWidget(self._progress_card)

        # ── 底部按钮 ──
        btn_layout_top = QHBoxLayout()
        btn_layout_top.setSpacing(10)

        self._diagnose_btn = self._make_primary_btn("开始智能检测")
        self._diagnose_btn.clicked.connect(self._on_start_diagnosis)
        btn_layout_top.addWidget(self._diagnose_btn)

        self._repair_btn = self._make_outline_btn("一键修复")
        self._repair_btn.clicked.connect(self._on_one_click_repair)
        btn_layout_top.addWidget(self._repair_btn)

        self._advanced_btn = self._make_outline_btn("高级修复")
        self._advanced_btn.clicked.connect(self._on_advanced_repair)
        btn_layout_top.addWidget(self._advanced_btn)

        layout.addLayout(btn_layout_top)

        btn_layout_bottom = QHBoxLayout()
        btn_layout_bottom.setSpacing(10)

        self._copy_btn = self._make_flat_btn("复制诊断结果")
        self._copy_btn.clicked.connect(self._on_copy_result)
        btn_layout_bottom.addWidget(self._copy_btn)

        self._export_btn = self._make_flat_btn("导出诊断日志")
        self._export_btn.clicked.connect(self._on_export_log)
        btn_layout_bottom.addWidget(self._export_btn)

        btn_layout_bottom.addStretch()

        self._close_btn = self._make_flat_btn("关闭")
        self._close_btn.clicked.connect(self.accept)
        btn_layout_bottom.addWidget(self._close_btn)

        layout.addLayout(btn_layout_bottom)

        # ── 应用全局样式 ──
        self.setStyleSheet("""
            QDialog {
                background-color: #F8F9FA;
            }
        """)

    # ====================================================================
    # 按钮工厂
    # ====================================================================

    def _make_primary_btn(self, text: str) -> QPushButton:
        """创建主按钮（蓝色渐变，同项目一致）"""
        btn = QPushButton(text)
        btn.setMinimumHeight(36)
        btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4DABF7, stop:1 #339AF0);
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #339AF0, stop:1 #228BE6);
            }
            QPushButton:disabled {
                background: #ADB5BD;
                color: #FFFFFF;
            }
        """)
        return btn

    def _make_outline_btn(self, text: str) -> QPushButton:
        """创建轮廓按钮（白底蓝边框，同项目 widgetSettingBtn 一致）"""
        btn = QPushButton(text)
        btn.setMinimumHeight(36)
        btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #339AF0;
                border-radius: 8px;
                padding: 8px 14px;
                color: #339AF0;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #EBF5FF;
                border: 1px solid #228BE6;
                color: #228BE6;
            }
            QPushButton:disabled {
                background: #F1F3F5;
                border: 1px solid #DDE3E9;
                color: #ADB5BD;
            }
        """)
        return btn

    def _make_flat_btn(self, text: str) -> QPushButton:
        """创建扁平按钮（灰字灰边框，同项目 bottomSettingBtn 一致）"""
        btn = QPushButton(text)
        btn.setMinimumHeight(34)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #DDE3E9;
                border-radius: 6px;
                padding: 6px 14px;
                color: #868E96;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                border-color: #339AF0;
                color: #339AF0;
            }
            QPushButton:disabled {
                color: #CED4DA;
                border-color: #E9ECEF;
            }
        """)
        return btn

    # ====================================================================
    # 状态管理
    # ====================================================================

    def _update_ui_for_state(self):
        """根据当前状态更新所有控件的启用/禁用和可见性"""
        s = self._state

        self._diagnose_btn.setEnabled(
            s in (_STATE_IDLE, _STATE_DIAGNOSIS_DONE, _STATE_REPAIR_DONE)
        )
        self._repair_btn.setEnabled(
            s in (_STATE_IDLE, _STATE_DIAGNOSIS_DONE, _STATE_REPAIR_DONE)
        )
        self._advanced_btn.setEnabled(
            s in (_STATE_IDLE, _STATE_DIAGNOSIS_DONE, _STATE_REPAIR_DONE)
        )
        self._copy_btn.setEnabled(
            s in (_STATE_DIAGNOSIS_DONE, _STATE_REPAIR_DONE)
        )
        self._export_btn.setEnabled(True)
        self._close_btn.setEnabled(s not in (_STATE_DIAGNOSING, _STATE_REPAIRING))

        # 进度区域可见性
        self._progress_card.setVisible(s in (_STATE_DIAGNOSING, _STATE_REPAIRING))

        # 检测进度时的按钮文字
        if s == _STATE_DIAGNOSING:
            self._diagnose_btn.setText("检测中...")
            self._repair_btn.setText("一键修复")
            self._advanced_btn.setText("高级修复")
        elif s == _STATE_REPAIRING:
            self._diagnose_btn.setText("开始智能检测")
            self._repair_btn.setText("修复中...")
            self._advanced_btn.setText("修复中...")
        else:
            self._diagnose_btn.setText("开始智能检测")
            self._repair_btn.setText("一键修复")
            self._advanced_btn.setText("高级修复")

    # ====================================================================
    # 更新健康卡片
    # ====================================================================

    def _update_health_card(self, report: DiagnosisReport):
        """根据诊断报告刷新顶部健康卡片"""
        level = report.health_level
        if level == NetworkHealthLevel.HEALTHY:
            self._health_icon.setText("🟢")
            self._health_card.setStyleSheet("""
                QFrame#healthCard {
                    background-color: #EBFBEE;
                    border: 1px solid #B2F2BB;
                    border-radius: 10px;
                }
            """)
            self._health_text.setText("网络正常")
            self._health_text.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #2B8A3E; border: none;"
            )
        elif level == NetworkHealthLevel.WARNING:
            self._health_icon.setText("🟡")
            self._health_card.setStyleSheet("""
                QFrame#healthCard {
                    background-color: #FFF9DB;
                    border: 1px solid #FFEC99;
                    border-radius: 10px;
                }
            """)
            self._health_text.setText("存在轻微异常")
            self._health_text.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #E67700; border: none;"
            )
        else:  # ERROR
            self._health_icon.setText("🔴")
            self._health_card.setStyleSheet("""
                QFrame#healthCard {
                    background-color: #FFF0F0;
                    border: 1px solid #FFD0D0;
                    border-radius: 10px;
                }
            """)
            self._health_text.setText("网络配置异常")
            self._health_text.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #E03131; border: none;"
            )

    # ====================================================================
    # 更新诊断列表
    # ====================================================================

    def _populate_diagnosis_list(self, report: DiagnosisReport):
        """填充诊断结果列表"""
        # 清除旧内容（包括占位提示）
        self._clear_layout(self._diag_layout)

        if not report.items:
            placeholder = QLabel("暂无诊断数据")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet(
                "color: #ADB5BD; font-size: 13px; padding: 24px 0; background: transparent;"
            )
            self._diag_layout.addWidget(placeholder)
            self._diag_layout.addStretch()
            self._conclusion_card.setVisible(False)
            return

        for item in report.items:
            row = QFrame()
            row.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 4, 8, 4)
            row_layout.setSpacing(10)

            # 图标
            icon = QLabel()
            icon.setFixedWidth(20)
            icon.setAlignment(Qt.AlignCenter)
            if item.level == DiagnosisLevel.OK:
                icon.setText("✔")
                icon_color = "#2B8A3E"
            elif item.level == DiagnosisLevel.WARNING:
                icon.setText("✖")
                icon_color = "#E03131"
            else:
                icon.setText("ℹ")
                icon_color = "#5C7CFA"
            icon.setStyleSheet(
                f"font-size: 15px; color: {icon_color}; font-weight: bold; "
                f"background: transparent;"
            )
            row_layout.addWidget(icon)

            # 名称
            name = QLabel(item.name)
            name.setFixedWidth(110)
            name.setStyleSheet(
                "font-size: 12px; font-weight: bold; color: #343A40;"
                "background: transparent;"
            )
            row_layout.addWidget(name)

            # 状态
            status = QLabel(item.status)
            status.setWordWrap(True)
            status.setStyleSheet(
                f"font-size: 12px; color: {'#2B8A3E' if item.level == DiagnosisLevel.OK else '#E03131' if item.level == DiagnosisLevel.WARNING else '#495057'}; "
                f"background: transparent;"
            )
            row_layout.addWidget(status, 1)

            # 可选：detail tooltip
            if item.detail:
                name.setToolTip(item.detail)
                row.setToolTip(item.detail)

            self._diag_layout.addWidget(row)

        self._diag_layout.addStretch()

        # 更新结论与建议
        if report.conclusion:
            self._conclusion_label.setText(f"结论：{report.conclusion}")
            self._recommend_label.setText(f"建议：{report.recommendation}")
            self._conclusion_card.setVisible(True)

    # ====================================================================
    # 工具方法
    # ====================================================================

    @staticmethod
    def _clear_layout(layout):
        """递归清空布局中的所有控件"""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                NetworkRepairDialog._clear_layout(item.layout())

    def _log(self, text: str):
        """向执行日志区域追加文字（线程安全——在主线程通过信号调用）"""
        self._log_text.append(text)
        # 自动滚动到底部
        scrollbar = self._log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ====================================================================
    # 异步诊断
    # ====================================================================

    def _on_start_diagnosis(self):
        """点击「开始智能检测」"""
        self._state = _STATE_DIAGNOSING
        self._update_ui_for_state()
        self._log_text.clear()
        self._progress_bar.setValue(0)
        self._step_label.setText("正在检测网络配置...")
        self._log("开始网络诊断...")

        def _run():
            try:
                report = run_full_diagnosis()
                self._diagnosis_finished.emit(report)
            except Exception as e:
                write_log("诊断", "异常", str(e))
                # 即使失败也发送一个空报告
                self._diagnosis_finished.emit(
                    DiagnosisReport(
                        conclusion=f"诊断过程发生异常：{e}",
                        recommendation="请重试或以管理员权限运行",
                    )
                )

        threading.Thread(target=_run, daemon=True).start()

    def _on_diagnosis_finished(self, report: DiagnosisReport):
        """（主线程）诊断完成"""
        self._report = report
        self._state = _STATE_DIAGNOSIS_DONE
        self._update_ui_for_state()

        self._update_health_card(report)
        self._populate_diagnosis_list(report)
        self._progress_bar.setValue(100)
        self._step_label.setText("诊断完成")
        self._log("诊断完成。")

        # 延迟隐藏进度
        QTimer.singleShot(800, lambda: self._progress_card.setVisible(False))

    # ====================================================================
    # 一键修复
    # ====================================================================

    def _on_one_click_repair(self):
        """点击「一键修复」"""
        self._state = _STATE_REPAIRING
        self._update_ui_for_state()
        self._log_text.clear()
        self._progress_bar.setValue(0)
        self._log("开始一键修复...")

        def _run():
            try:
                result = self._repair_service.one_click_repair(
                    progress_callback=self._emit_progress,
                )
                if result[0] == ELEVATION_REQUIRED:
                    self._repair_finished.emit(None, None)  # 特殊值表示需要提权
                    return
                success, report = result
                self._repair_finished.emit(success, report)
            except Exception as e:
                write_log("一键修复", "异常", str(e))
                self._repair_finished.emit(False, None)

        threading.Thread(target=_run, daemon=True).start()

    # ====================================================================
    # 高级修复
    # ====================================================================

    def _on_advanced_repair(self):
        """点击「高级修复」"""
        reply = QMessageBox.question(
            self,
            "高级修复",
            "高级修复将执行以下操作：\n"
            "• 重置 Winsock\n"
            "• 重置 TCP/IP\n"
            "• 重置 WinHTTP 代理\n"
            "• 刷新 DNS 缓存\n"
            "• 释放/重新获取 IP 地址\n"
            "• 重启网络适配器\n"
            "• 重置 IPv4/IPv6 配置\n\n"
            "这可能导致网络短暂中断。\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._state = _STATE_REPAIRING
        self._update_ui_for_state()
        self._log_text.clear()
        self._progress_bar.setValue(0)
        self._log("开始高级修复...")

        def _run():
            try:
                result = self._repair_service.advanced_repair(
                    progress_callback=self._emit_progress,
                )
                if result[0] == ELEVATION_REQUIRED:
                    self._repair_finished.emit(None, None)
                    return
                success, report = result
                self._repair_finished.emit(success, report)
            except Exception as e:
                write_log("高级修复", "异常", str(e))
                self._repair_finished.emit(False, None)

        threading.Thread(target=_run, daemon=True).start()

    # ====================================================================
    # 修复进度反馈
    # ====================================================================

    def _emit_progress(self, progress: RepairProgress):
        """从后台线程发送进度信号"""
        self._repair_progress.emit(progress)

    def _on_repair_progress(self, progress: RepairProgress):
        """（主线程）更新修复进度"""
        self._step_label.setText(progress.current_step)
        if progress.total > 0:
            pct = int(progress.completed * 100 / progress.total)
            self._progress_bar.setValue(min(pct, 99))
        if progress.log:
            self._log(progress.log)

    # ====================================================================
    # 修复完成
    # ====================================================================

    def _request_elevation(self):
        """请求管理员权限重启"""
        reply = QMessageBox.question(
            self,
            "需要管理员权限",
            "当前操作需要管理员权限才能执行。\n\n"
            "是否以管理员身份重新启动程序？\n\n"
            "（这不会影响正在运行的定时任务）",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            write_log("提权", "请求中", "用户确认提权")
            ok = RepairService.request_elevation()
            if not ok:
                QMessageBox.warning(
                    self, "提权失败",
                    "提权被取消或失败，修复操作已取消。\n"
                    "您可以手动以管理员身份运行本程序后再试。",
                )
            else:
                # 提权成功，当前进程准备退出
                self.accept()
                QApplication.quit()
        else:
            write_log("提权", "取消", "用户拒绝提权")
            QMessageBox.information(
                self, "已取消",
                "修复操作已取消，不影响程序其他功能。",
            )

    def _on_repair_finished(self, success: bool, report: Optional[DiagnosisReport]):
        """（主线程）修复完成"""
        # 处理提权请求
        if success is None and report is None:
            self._state = _STATE_IDLE
            self._update_ui_for_state()
            self._progress_card.setVisible(False)
            self._request_elevation()
            return

        self._progress_bar.setValue(100)
        self._log("修复完成，正在重新检测...")
        self._step_label.setText("修复完成，正在验证...")

        # 修复后自动重检测
        def _run_quick_check():
            try:
                report = quick_check_after_repair()
                self._quick_check_finished.emit(report)
            except Exception as e:
                write_log("修复验证", "异常", str(e))
                self._quick_check_finished.emit(
                    DiagnosisReport(conclusion=f"验证异常：{e}")
                )

        threading.Thread(target=_run_quick_check, daemon=True).start()

    def _on_quick_check_finished(self, report: DiagnosisReport):
        """（主线程）修复后验证完成"""
        self._report = report
        self._state = _STATE_REPAIR_DONE
        self._update_ui_for_state()

        self._update_health_card(report)
        self._populate_diagnosis_list(report)

        if report.health_level == NetworkHealthLevel.HEALTHY:
            self._log("🎉 网络修复成功，所有指标正常。")
        else:
            self._log(f"⚠ 部分异常仍存在（{report.warning_count} 项），建议执行高级修复或重启电脑。")

        QTimer.singleShot(500, lambda: self._progress_card.setVisible(False))

    # ====================================================================
    # 复制 / 导出
    # ====================================================================

    def _on_copy_result(self):
        """复制诊断结果到剪贴板"""
        if not self._report:
            QMessageBox.information(self, "提示", "暂无诊断结果可复制。")
            return
        text = self._report.to_text()
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "已复制", "诊断结果已复制到剪贴板。")

    def _on_export_log(self):
        """导出诊断日志"""
        # 生成默认文件名（Windows 文件名不能含 :）
        if self._report and self._report.timestamp:
            ts = self._report.timestamp.replace(":", "-").replace(" ", "_")
            default_name = f"网络诊断日志_{ts}.txt"
        else:
            default_name = "网络诊断日志.txt"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出诊断日志",
            default_name,
            "文本文件 (*.txt);;所有文件 (*)",
        )
        if path:
            ok = export_logs(path)
            if ok:
                QMessageBox.information(self, "导出成功", f"日志已导出至：\n{path}")
            else:
                QMessageBox.warning(self, "导出失败", "日志导出失败，请检查路径权限。")
