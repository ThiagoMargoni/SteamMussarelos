from __future__ import annotations

from PySide6.QtCore import QByteArray, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

_SERVER_NAME = "SteamMussarelosSingleInstance"

class SingleInstance(QObject):
    activated = Signal()

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._server: QLocalServer | None = None

    def activate_existing(self) -> bool:
        socket = QLocalSocket(self)
        socket.connectToServer(_SERVER_NAME)
        if not socket.waitForConnected(400):
            socket.abort()
            return False
        socket.write(QByteArray(b"raise\n"))
        socket.flush()
        socket.waitForBytesWritten(400)
        socket.disconnectFromServer()
        if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            socket.waitForDisconnected(400)
        return True

    def start_server(self) -> bool:
        if self.activate_existing():
            return False
        QLocalServer.removeServer(_SERVER_NAME)
        server = QLocalServer(self)
        if not server.listen(_SERVER_NAME):
            QLocalServer.removeServer(_SERVER_NAME)
            if not server.listen(_SERVER_NAME):
                return not self.activate_existing()
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        return True

    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(lambda s=socket: self._read_socket(s))
            if socket.bytesAvailable():
                self._read_socket(socket)

    def _read_socket(self, socket: QLocalSocket) -> None:
        raw = bytes(socket.readAll()).decode("utf-8", errors="ignore")
        socket.disconnectFromServer()
        socket.deleteLater()
        if "raise" in raw:
            self.activated.emit()
