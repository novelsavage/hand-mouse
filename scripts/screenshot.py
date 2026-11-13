"""README screenshot with an illustrated preview, never a personal camera frame."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import QApplication, Window, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt
app = QApplication([])
w = Window()
w.show()
def save():
    pix = QPixmap(720, 420)
    pix.fill(QColor('#14202b'))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor('#44dcb4'), 8))
    fingers = [[(290,270),(230,220),(195,160)], [(300,245),(280,155),(275,80)],
               [(335,240),(335,135),(335,55)],[(370,245),(390,150),(398,80)],
               [(395,265),(445,200),(460,140)]]
    for finger in fingers:
        previous = (345,340)
        for point in finger:
            p.drawLine(*previous, *point)
            p.setBrush(QColor('#ffc847'))
            p.drawEllipse(point[0]-5,point[1]-5,10,10)
            previous = point
    p.setPen(QColor('#dce8f2'))
    p.setFont(QFont('Sans Serif', 12))
    p.drawText(20, 35, 'ILLUSTRATED PREVIEW / camera frames stay local')
    p.end()
    w.preview.setPixmap(pix.scaled(w.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    w.grab().save(str(Path(__file__).resolve().parents[1]/'docs/screenshot.png'))
    w.close()
    app.quit()
QTimer.singleShot(500, save)
app.exec()
