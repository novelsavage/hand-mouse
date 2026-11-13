"""Local artwork exhibition with open-palm page gestures. No OS input injection."""
import argparse
import json
import os
import re
import signal
import sys
import time
from pathlib import Path

# Reuse the camera/landmark worker; importing it never creates a virtual mouse.
from main import Camera
from PySide6.QtCore import Qt, QTimer, QRectF, QStandardPaths
from PySide6.QtGui import (QColor, QPainter, QPen, QPixmap, QImageReader,
                          QKeySequence, QShortcut, QFont, QImage, QIcon)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QFileDialog, QComboBox, QProgressBar)
from PySide6.QtNetwork import QLocalSocket, QLocalServer
from swipe import PageGesture


def list_images(folder):
    supported = {bytes(f).decode().lower() for f in QImageReader.supportedImageFormats()}
    # Raster artwork only. HEIC originals may coexist with converted PNGs.
    supported &= {'png','jpg','jpeg','webp','bmp','tif','tiff','heic','heif'}
    selected = {}
    priority = {'png':0, 'jpg':1, 'jpeg':1, 'webp':2}
    for path in Path(folder).iterdir():
        ext = path.suffix[1:].lower()
        if path.is_file() and ext in supported:
            key = path.stem.casefold()
            if key not in selected or priority.get(ext,9) < priority.get(selected[key].suffix[1:].lower(),9):
                selected[key] = path
    return sorted(selected.values(), key=lambda p: [int(t) if t.isdigit() else t.casefold()
                                                    for t in re.split(r'(\d+)',p.name)])


class Artwork(QWidget):
    def __init__(self):
        super().__init__()
        self.pixmap = QPixmap()
        self.setMinimumSize(300, 220)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#e8e3da'))
        area = self.rect().adjusted(30,22,-30,-22)
        if self.pixmap.isNull():
            p.setPen(QColor('#756d61'))
            p.drawText(area, Qt.AlignCenter, '作品フォルダーを選んでください\nPNG / JPEG / WebP などに対応')
            return
        size = self.pixmap.size().scaled(area.size(), Qt.KeepAspectRatio)
        x, y = (self.width()-size.width())/2, (self.height()-size.height())/2
        p.fillRect(QRectF(x-9,y-9,size.width()+18,size.height()+18), QColor('#c9c3b9'))
        p.fillRect(QRectF(x-7,y-7,size.width()+14,size.height()+14), Qt.white)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(round(x),round(y),size.width(),size.height(),self.pixmap)


class HandGuide(QWidget):
    def __init__(self):
        super().__init__()
        self.hand = None
        self.ready = False
        self.setFixedSize(180,100)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#e8e3da'))
        p.setPen(QPen(QColor('#b9b1a4'), 1, Qt.DashLine))
        p.drawRoundedRect(QRectF(.36*self.width(),.15*self.height(),.28*self.width(),.70*self.height()),5,5)
        if not self.hand:
            p.setPen(QColor('#776f63'))
            p.drawText(self.rect(),Qt.AlignCenter,'ここに手の骨格を表示')
            return
        from main import CONNECTIONS
        points = [(lm.x*self.width(),lm.y*self.height()) for lm in self.hand]
        p.setPen(QPen(QColor('#227464' if self.ready else '#8c6942'),2))
        for a,b in CONNECTIONS:
            p.drawLine(round(points[a][0]),round(points[a][1]),round(points[b][0]),round(points[b][1]))
        for x,y in points:
            p.drawEllipse(QRectF(x-2,y-2,4,4))


class Gallery(QMainWindow):
    def __init__(self, folder=None, camera=0, remember=True):
        super().__init__()
        self.setWindowTitle('Hand Gallery · 作品展示')
        self.setWindowIcon(QIcon.fromTheme('image-x-generic'))
        self.resize(1120,850)
        self.worker = None
        self.files = []
        self.index = 0
        self.gesture = PageGesture()
        self.last_frame = 0
        self.remember = remember
        config = Path(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation))
        self.settings_path = config/'gallery.json'
        self.folder = None
        self.frame_count = 0
        self.setStyleSheet('''QMainWindow,QWidget {background:#f6f3ed;color:#302f2b;}
            QLabel#heading {font-size:25px;font-weight:700;}
            QLabel#count {color:#756d61;font-size:15px;}
            QLabel#instruction {font-size:20px;font-weight:600;}
            QPushButton {padding:9px 16px;border:1px solid #cfc6b8;border-radius:6px;background:#fffdf9;}
            QPushButton:hover {background:#e8e3da;}
            QPushButton#camera {background:#246b5c;color:white;border:0;}
            QComboBox {padding:6px;min-width:150px;}
            QProgressBar {border:0;background:#dcd5ca;height:4px;}
            QProgressBar::chunk {background:#246b5c;}''')
        base = QWidget()
        self.setCentralWidget(base)
        layout = QVBoxLayout(base)
        layout.setContentsMargins(24,18,24,16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        heading = QLabel('みんなの作品展')
        heading.setObjectName('heading')
        header.addWidget(heading)
        header.addStretch()
        self.count = QLabel('作品を選択')
        self.count.setObjectName('count')
        header.addWidget(self.count)
        layout.addLayout(header)
        self.art = Artwork()
        layout.addWidget(self.art,1)
        info = QHBoxLayout()
        self.title = QLabel('フォルダーの画像を、そのまま展示できます')
        self.title.setStyleSheet('font-size:18px;')
        info.addWidget(self.title,1)
        self.previous = QPushButton('← 前の作品')
        self.previous.clicked.connect(lambda: self.turn(-1))
        self.next = QPushButton('次の作品 →')
        self.next.clicked.connect(lambda: self.turn(1))
        info.addWidget(self.previous)
        info.addWidget(self.next)
        layout.addLayout(info)
        footer = QHBoxLayout()
        self.guide = HandGuide()
        footer.addWidget(self.guide)
        instructions = QVBoxLayout()
        self.message = QLabel('カメラを開始して、手で作品をめくってみよう')
        self.message.setObjectName('instruction')
        self.message.setWordWrap(True)
        instructions.addWidget(self.message)
        self.progress = QProgressBar()
        self.progress.setRange(0,100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(4)
        instructions.addWidget(self.progress)
        help_text = QLabel('開いた手を一瞬止める → 左へ軽く動かすと次 / 右なら前\n1回ずつ切り替わります。画面内の広い範囲から軽く動かせます。')
        help_text.setWordWrap(True)
        help_text.setStyleSheet('color:#756d61;')
        instructions.addWidget(help_text)
        footer.addLayout(instructions,1)
        layout.addLayout(footer)
        self.toolbar = QWidget()
        controls = QHBoxLayout(self.toolbar)
        controls.setContentsMargins(0,0,0,0)
        choose = QPushButton('作品フォルダーを選ぶ')
        choose.clicked.connect(self.choose_folder)
        controls.addWidget(choose)
        self.cameras = QComboBox()
        for path in sorted(Path('/sys/class/video4linux').glob('video*')):
            self.cameras.addItem(f'{path.name} · {(path/"name").read_text().strip()}', int(path.name[5:]))
        if self.cameras.findData(camera) >= 0:
            self.cameras.setCurrentIndex(self.cameras.findData(camera))
        controls.addWidget(self.cameras,1)
        self.camera_button = QPushButton('カメラ開始')
        self.camera_button.setObjectName('camera')
        self.camera_button.clicked.connect(self.toggle_camera)
        controls.addWidget(self.camera_button)
        fullscreen = QPushButton('全画面 F11')
        fullscreen.clicked.connect(self.toggle_fullscreen)
        controls.addWidget(fullscreen)
        layout.addWidget(self.toolbar)
        self.notice = QLabel('カメラ停止中 · 画像は端末内で表示します · F11:全画面 / Space:カメラ開始・停止 / Esc:全画面解除・停止')
        self.notice.setStyleSheet('font-size:12px;color:#756d61;')
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        for key,callback in [('Right',lambda:self.turn(1)),('Left',lambda:self.turn(-1)),
                            ('F11',self.toggle_fullscreen),('Escape',self.escape),('Space',self.toggle_camera)]:
            shortcut = QShortcut(QKeySequence(key),self)
            shortcut.activated.connect(callback)
        self.watchdog = QTimer(self)
        self.watchdog.timeout.connect(self.check_camera)
        self.watchdog.start(250)
        if folder is None and remember:
            try:
                folder = json.loads(self.settings_path.read_text()).get('folder')
            except (OSError,ValueError):
                pass
        if folder:
            self.load_folder(folder)
        else:
            self.update_buttons()

    def choose_folder(self):
        # Pause recognition while the operator uses the chooser.
        self.stop_camera()
        folder = QFileDialog.getExistingDirectory(self,'作品フォルダーを選択',str(self.folder or Path.home()/'Pictures'))
        if folder:
            self.load_folder(folder)

    def load_folder(self, folder):
        try:
            files = list_images(folder)
        except OSError as exc:
            self.message.setText(f'フォルダーを開けません: {exc}')
            return False
        if not files:
            self.message.setText('表示できる画像がありません。PNGやJPEGのフォルダーを選んでください。')
            return False
        self.files = files
        self.folder = Path(folder)
        self.index = 0
        if self.remember:
            self.settings_path.parent.mkdir(parents=True,exist_ok=True)
            self.settings_path.write_text(json.dumps({'folder':str(self.folder)},ensure_ascii=False))
        self.show_artwork()
        self.message.setText('カメラを開始して、手で作品をめくってみよう')
        return True

    def update_buttons(self):
        self.previous.setEnabled(len(self.files)>1)
        self.next.setEnabled(len(self.files)>1)
        self.camera_button.setEnabled(bool(self.files))

    def show_artwork(self):
        path = self.files[self.index]
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            reader.setScaledSize(size.scaled(1920,1200,Qt.KeepAspectRatio))
        image = reader.read()
        self.art.pixmap = QPixmap.fromImage(image)
        self.art.update()
        self.title.setText(path.stem)
        self.count.setText(f'{self.index+1:03d} / {len(self.files):03d}')
        self.update_buttons()
        if image.isNull():
            self.message.setText(f'画像を読み込めません: {path.name} · 矢印キーで次に進めます')

    def turn(self, direction):
        if len(self.files)<2:
            return
        self.index = (self.index+direction)%len(self.files)
        self.show_artwork()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.toolbar.show()
        else:
            self.showFullScreen()
            self.toolbar.hide()

    def escape(self):
        self.stop_camera()
        if self.isFullScreen():
            self.toggle_fullscreen()

    def toggle_camera(self):
        if self.worker:
            self.stop_camera()
            return
        if not self.files:
            return
        self.gesture.reset()
        self.last_frame = time.monotonic()
        self.worker = Camera(self.cameras.currentData() or 0)
        self.worker.frame.connect(self.on_frame)
        self.worker.error.connect(self.camera_error)
        self.worker.start()
        self.cameras.setEnabled(False)
        self.camera_button.setText('カメラ停止')
        self.message.setText('カメラを準備しています…')
        self.notice.setText('画像・カメラ映像は端末内で処理します · カメラ映像は表示・保存しません · Esc:停止')

    def on_frame(self, rgb, hand, captured):
        if not self.worker or time.monotonic()-captured > .5:
            return
        self.last_frame = captured
        self.frame_count += 1
        result = self.gesture.update(hand,captured)
        self.guide.hand = hand
        self.guide.ready = result.progress >= 1
        self.guide.update()
        if result.page:
            self.turn(result.page)
        self.message.setText(result.message)
        self.progress.setValue(round(result.progress*100))

    def check_camera(self):
        if self.worker and time.monotonic()-self.last_frame > 1.5:
            self.gesture.reset()
            self.guide.hand = None
            self.guide.update()
            self.progress.setValue(0)
            self.message.setText('映像を待っています。改善しない場合はカメラを選び直してください。')

    def camera_error(self, text):
        self.stop_camera()
        self.message.setText(text)

    def stop_camera(self):
        worker,self.worker = self.worker,None
        if worker:
            worker.requestInterruption()
            worker.wait()
        self.gesture.reset()
        self.guide.hand = None
        self.guide.update()
        self.progress.setValue(0)
        self.camera_button.setText('カメラ開始')
        self.cameras.setEnabled(True)
        self.message.setText('手の操作は停止中 · ボタンや矢印キーでも作品をめくれます')
        self.notice.setText('カメラ停止中 · F11:全画面 / Space:カメラ開始・停止 / Esc:全画面解除・停止')

    def closeEvent(self,event):
        self.stop_camera()
        event.accept()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images',type=Path)
    parser.add_argument('--camera',type=int,default=0)
    parser.add_argument('--fullscreen',action='store_true')
    args=parser.parse_args()
    app=QApplication(sys.argv[:1])
    app.setApplicationName('Hand Gallery')
    name=f'hand-gallery-{os.getuid()}'
    client=QLocalSocket()
    client.connectToServer(name)
    if client.waitForConnected(300):
        client.write(json.dumps({'folder':str(args.images) if args.images else None}).encode())
        client.waitForBytesWritten(500)
        return
    server=QLocalServer()
    server.setSocketOptions(QLocalServer.UserAccessOption)
    QLocalServer.removeServer(name)
    if not server.listen(name):
        raise RuntimeError(server.errorString())
    w=Gallery(args.images,args.camera)
    def accept():
        socket=server.nextPendingConnection()
        def read():
            folder=json.loads(bytes(socket.readAll()).decode()).get('folder')
            w.stop_camera()
            if folder:
                w.load_folder(folder)
            w.showNormal()
            w.toolbar.show()
            w.raise_()
            socket.disconnectFromServer()
        socket.readyRead.connect(read)
        socket.disconnected.connect(socket.deleteLater)
        if socket.bytesAvailable(): read()
    server.newConnection.connect(accept)
    signal.signal(signal.SIGINT,lambda *_:w.close())
    signal.signal(signal.SIGTERM,lambda *_:w.close())
    w.show()
    if args.fullscreen: w.toggle_fullscreen()
    sys.exit(app.exec())


if __name__=='__main__':
    main()
