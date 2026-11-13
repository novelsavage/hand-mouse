"""Create a gallery screenshot using generated test shapes, never user photos."""
import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gallery import QApplication,Gallery,QTimer
from PySide6.QtGui import QImage,QColor,QPainter,QPolygonF,QFont
from PySide6.QtCore import QPointF,Qt
app=QApplication([])
temporary=tempfile.TemporaryDirectory()
folder=Path(temporary.name)
image=QImage(1100,680,QImage.Format_RGB32)
image.fill(QColor('#d4e3e1'))
p=QPainter(image)
p.setRenderHint(QPainter.Antialiasing)
p.setPen(Qt.NoPen)
p.setBrush(QColor('#e6b867'))
p.drawEllipse(770,75,110,110)
p.setBrush(QColor('#96b7ad'))
p.drawPolygon(QPolygonF([QPointF(0,470),QPointF(250,200),QPointF(610,680),QPointF(0,680)]))
p.setBrush(QColor('#5d8a80'))
p.drawPolygon(QPolygonF([QPointF(300,680),QPointF(780,250),QPointF(1100,610),QPointF(1100,680)]))
p.setBrush(QColor('#2e605a'))
p.drawPolygon(QPolygonF([QPointF(0,570),QPointF(1100,500),QPointF(1100,680),QPointF(0,680)]))
p.setPen(QColor('#244b46'))
p.setFont(QFont('Sans Serif',16))
p.drawText(35,50,'SAMPLE / generated test image')
p.end()
image.save(str(folder/'サンプル作品.png'))
w=Gallery(folder,remember=False)
w.show()
def save():
    w.grab().save(str(Path(__file__).resolve().parents[1]/'docs/gallery.png'))
    w.close()
    app.quit()
QTimer.singleShot(500,save)
app.exec()
temporary.cleanup()
