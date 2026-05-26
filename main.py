# --------------------------------------------------------------------------
# 文件：main.py
# 作用：程序入口，负责单实例保护与应用启动
# --------------------------------------------------------------------------

import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSharedMemory
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from ui.main_window import MainWindow


def main():
    """程序的启动函数"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口时不退出（隐藏到系统托盘）

    # ---- 单实例保护 ----
    shared_memory = QSharedMemory("AutoShutdownApp_SingleInstance")
    if not shared_memory.create(1):
        # 已有实例在运行，通过本地 Socket 通知它显示窗口
        socket = QLocalSocket()
        socket.connectToServer("AutoShutdownApp_IPC")
        if socket.waitForConnected(1000):
            socket.write(b"show")
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
        return  # 退出当前实例

    # 清理可能残留的 IPC 服务器（上次异常退出时）
    QLocalServer.removeServer("AutoShutdownApp_IPC")
    ipc_server = QLocalServer()
    ipc_server.listen("AutoShutdownApp_IPC")

    window = MainWindow()
    window.show()

    # 监听其他实例发来的 IPC 信号
    def on_new_connection():
        conn = ipc_server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(window.show_window_from_other_instance)
            conn.readyRead.connect(lambda c=conn: c.deleteLater())

    ipc_server.newConnection.connect(on_new_connection)

    # 存储引用防止被 Python 垃圾回收
    app._ipc_server = ipc_server

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
