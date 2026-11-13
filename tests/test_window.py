import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
import numpy as np
import pytest
from main import QApplication, Window
from control import GestureControl
from test_control import Mouse, hand


class CameraStub:
    def requestInterruption(self): pass
    def wait(self): pass


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    w = Window()
    w.worker = CameraStub()
    w.mouse = Mouse()
    w.mouse.close = lambda: None
    w.control = GestureControl(w.mouse)
    yield w
    w.close()


def test_camera_frame_and_pause_release_button(window):
    window.active = True
    window.on_frame(np.zeros((480, 640, 3), dtype=np.uint8), hand(True), time.monotonic())
    assert window.control.holding
    window.pause()
    assert not window.active
    assert window.mouse.events[-1] == ('button', False)
    assert not window.preview.pixmap().isNull()


def test_stalled_camera_pauses_and_releases(window):
    window.active = True
    window.control.update(hand(True))
    window.last_frame = time.monotonic()-2
    window.check_stale()
    assert not window.active
    assert window.mouse.events[-1] == ('button', False)


def test_stale_queued_frame_cannot_move_mouse(window):
    window.active = True
    window.on_frame(np.zeros((480, 640, 3), dtype=np.uint8), hand(True), time.monotonic()-2)
    assert window.mouse.events == []
