"""KDE hand mouse. Starts paused; camera frames stay on this computer."""
import argparse
import os
import signal
import sys
import time
from pathlib import Path
from urllib.request import urlretrieve

# OpenCV wheels may override Qt's plugin directory. Use PySide's own plugins.
import cv2
for key in ("QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_FONTDIR"):
    if "cv2" in os.environ.get(key, ""):
        os.environ.pop(key)
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions, RunningMode
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QImage, QPixmap, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QComboBox, QCheckBox, QSlider, QSystemTrayIcon, QMenu)
from control import GestureControl, LinuxMouse

ROOT = Path(__file__).resolve().parent
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
CONNECTIONS = ((0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),
               (9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),
               (13,17),(17,18),(18,19),(19,20),(0,17))


class Camera(QThread):
    frame = Signal(object, object, float)
    error = Signal(str)

    def __init__(self, index):
        super().__init__()
        self.index = index

    def run(self):
        cap = None
        try:
            path = ROOT / "models/hand_landmarker.task"
            if not path.exists():
                path.parent.mkdir(exist_ok=True)
                temporary = path.with_suffix(".download")
                urlretrieve(MODEL_URL, temporary)
                temporary.replace(path)
            cap = cv2.VideoCapture(self.index, cv2.CAP_V4L2)
            if not cap.isOpened():
                raise RuntimeError(f"カメラ {self.index} を開けません。ほかのアプリの使用状況を確認してください。")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            options = HandLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(path)),
                running_mode=RunningMode.VIDEO, num_hands=1)
            with HandLandmarker.create_from_options(options) as detector:
                stamp = 0
                while not self.isInterruptionRequested():
                    ok, frame = cap.read()
                    if not ok:
                        raise RuntimeError("カメラから映像を取得できませんでした。")
                    rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
                    stamp = max(stamp+1, int(time.monotonic()*1000))
                    result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), stamp)
                    hand = result.hand_landmarks[0] if result.hand_landmarks else None
                    if hand:
                        points = [(int(p.x*rgb.shape[1]), int(p.y*rgb.shape[0])) for p in hand]
                        for a,b in CONNECTIONS:
                            cv2.line(rgb, points[a], points[b], (68,220,180), 2)
                        for p in points:
                            cv2.circle(rgb, p, 4, (255,200,70), -1)
                    self.frame.emit(rgb, hand, time.monotonic())
                    self.msleep(20)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            if cap is not None:
                cap.release()


class Window(QMainWindow):
    def __init__(self, camera=0):
        super().__init__()
        self.setWindowTitle("Hand Mouse")
        self.resize(820, 740)
        self.worker = self.mouse = self.control = None
        self.active = False
        self.last_frame = 0
        self.setWindowIcon(QIcon.fromTheme("input-mouse"))
        base = QWidget()
        self.setCentralWidget(base)
        layout = QVBoxLayout(base)
        title = QLabel("Hand Mouse")
        title.setStyleSheet("font-size: 30px; font-weight: 700; padding: 10px 0;")
        layout.addWidget(title)
        layout.addWidget(QLabel("手の動きでカーソル移動。握るとドラッグ、開くと解除。"))
        self.preview = QLabel("カメラを選び「プレビュー開始」を押してください")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(640, 400)
        self.preview.setStyleSheet("background:#14202b; color:#dce8f2; border-radius:12px;")
        layout.addWidget(self.preview, 1)
        self.status = QLabel("一時停止 · マウスは動きません")
        self.status.setStyleSheet("font-size:18px; padding:8px;")
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.cameras = QComboBox()
        for path in sorted(Path("/sys/class/video4linux").glob("video*")):
            index = int(path.name[5:])
            self.cameras.addItem(f"{path.name} · {(path/'name').read_text().strip()}", index)
        if self.cameras.findData(camera) >= 0:
            self.cameras.setCurrentIndex(self.cameras.findData(camera))
        row.addWidget(self.cameras, 1)
        self.camera_button = QPushButton("プレビュー開始")
        self.camera_button.clicked.connect(self.toggle_camera)
        row.addWidget(self.camera_button)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.toggle = QPushButton("操作開始")
        self.toggle.setMinimumHeight(44)
        self.toggle.clicked.connect(self.toggle_control)
        self.toggle.setEnabled(False)
        row.addWidget(self.toggle)
        stop = QPushButton("終了")
        stop.clicked.connect(self.close)
        row.addWidget(stop)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("動きの追従速度"))
        self.smoothing = QSlider(Qt.Horizontal)
        self.smoothing.setRange(5, 80)
        self.smoothing.setValue(25)
        row.addWidget(self.smoothing)
        self.scroll = QCheckBox("指の開閉でスクロール")
        row.addWidget(self.scroll)
        layout.addLayout(row)
        hint = QLabel("F8: 開始 / 一時停止　Esc: 一時停止（このウィンドウ内）\n"
                      "ほかのアプリ操作中はトレイの「一時停止」を使えます。手を画面外に出してもドラッグを解除します。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        for key, callback in (("F8", self.toggle_control), ("Escape", self.pause)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("Hand Mouse · 一時停止")
        menu = QMenu(self)
        menu.addAction("ウィンドウを表示", self.showNormal)
        menu.addAction("一時停止", self.pause)
        menu.addAction("終了", self.close)
        self.tray.setContextMenu(menu)
        self.tray.show()
        self.watchdog = QTimer(self)
        self.watchdog.timeout.connect(self.check_stale)
        self.watchdog.start(200)

    def toggle_camera(self):
        if self.worker:
            self.stop_camera()
            return
        self.worker = Camera(self.cameras.currentData() or 0)
        self.worker.frame.connect(self.on_frame)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        self.cameras.setEnabled(False)
        self.camera_button.setText("カメラ停止")

    def toggle_control(self):
        if self.active:
            self.pause()
            return
        if not self.worker or time.monotonic()-self.last_frame > 1:
            return
        try:
            if self.mouse is None:
                self.mouse = LinuxMouse()
                self.control = GestureControl(self.mouse)
            self.active = True
            self.toggle.setText("一時停止")
            self.tray.setToolTip("Hand Mouse · 操作中")
        except Exception as exc:
            self.on_error(f"仮想マウスを作成できません: {exc}\nREADMEの /dev/uinput 設定を確認してください。")

    def pause(self):
        self.active = False
        if self.control:
            self.control.release()
        self.toggle.setText("操作開始")
        self.status.setText("一時停止 · マウスは動きません")
        self.tray.setToolTip("Hand Mouse · 一時停止")

    def check_stale(self):
        if self.active and time.monotonic()-self.last_frame > 0.8:
            self.pause()
            self.status.setText("映像が途切れたため一時停止しました")

    def on_frame(self, rgb, hand, captured):
        # Discard queued frames after stopping or if inference/UI has fallen behind.
        if not self.worker or time.monotonic()-captured > 0.5:
            return
        self.last_frame = captured
        self.toggle.setEnabled(True)
        if self.active:
            try:
                self.status.setText(self.control.update(hand, self.smoothing.value()/100, scroll=self.scroll.isChecked()))
            except Exception as exc:
                self.on_error(str(exc))
        image = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888).copy()
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def on_error(self, text):
        self.pause()
        self.status.setText(text)
        self.status.setWordWrap(True)

    def stop_camera(self):
        self.pause()
        if self.worker:
            self.worker.requestInterruption()
            self.worker.wait()
            self.worker = None
        self.toggle.setEnabled(False)
        self.cameras.setEnabled(True)
        self.camera_button.setText("プレビュー開始")
        self.preview.clear()
        self.preview.setText("カメラ停止中")

    def closeEvent(self, event):
        self.stop_camera()
        if self.mouse:
            self.mouse.close()
        self.tray.hide()
        event.accept()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--pause", action="store_true", help="Pause an already running instance")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Hand Mouse")
    name = f"hand-mouse-{os.getuid()}"
    client = QLocalSocket()
    client.connectToServer(name)
    if client.waitForConnected(300):
        client.write(b"pause" if args.pause else b"show")
        client.waitForBytesWritten(500)
        return
    if args.pause:
        return
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.UserAccessOption)
    # A previous crash can leave a stale socket; the connection above ruled out a live instance.
    QLocalServer.removeServer(name)
    if not server.listen(name):
        raise RuntimeError(server.errorString())
    window = Window(args.camera)
    def accept_command():
        socket = server.nextPendingConnection()
        def read_command():
            command = bytes(socket.readAll())
            if command == b"pause":
                window.pause()
            else:
                window.showNormal()
                window.raise_()
            socket.disconnectFromServer()
        socket.readyRead.connect(read_command)
        socket.disconnected.connect(socket.deleteLater)
        if socket.bytesAvailable():
            read_command()
    server.newConnection.connect(accept_command)
    signal.signal(signal.SIGINT, lambda *_: window.close())
    signal.signal(signal.SIGTERM, lambda *_: window.close())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
