import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
import pytest
from PySide6.QtGui import QImage, QColor
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from gallery import QApplication, Gallery, list_images
from test_swipe import hand


@pytest.fixture
def gallery(tmp_path):
    app=QApplication.instance() or QApplication([])
    for name,color in [('作品2.png','red'),('作品10.png','blue'),('作品1.png','green')]:
        image=QImage(120,80,QImage.Format_RGB32)
        image.fill(QColor(color))
        image.save(str(tmp_path/name))
    w=Gallery(tmp_path,remember=False)
    w.show()
    app.processEvents()
    yield w
    w.worker=None
    w.close()


def test_image_loading_natural_order_and_keyboard(gallery):
    w=gallery
    assert [p.name for p in w.files]==['作品1.png','作品2.png','作品10.png']
    assert not w.art.pixmap.isNull()
    QTest.keyClick(w,Qt.Key_Right)
    assert w.index==1
    QTest.keyClick(w,Qt.Key_Left)
    assert w.index==0
    w.turn(-1)
    assert w.index==2


def test_landmarks_change_exactly_one_artwork(gallery):
    w=gallery
    w.worker=object()
    start=time.monotonic()
    # Times are recent enough to pass the UI's stale-frame filter.
    w.on_frame(None,hand(),start-.4)
    w.on_frame(None,hand(),start)
    w.on_frame(None,hand(.25),start+.15)
    assert w.index==1
    w.on_frame(None,hand(.5),start+.3)
    assert w.index==1


def test_old_frame_cannot_change_artwork(gallery):
    w=gallery
    w.worker=object()
    w.on_frame(None,hand(.2),time.monotonic()-3)
    assert w.index==0
    assert w.frame_count==0


def test_bad_folder_retains_current_exhibition(gallery,tmp_path):
    before=list(gallery.files)
    assert not gallery.load_folder(tmp_path/'missing')
    assert gallery.files==before
