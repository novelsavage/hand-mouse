from types import SimpleNamespace as P
from control import GestureControl


class Mouse:
    def __init__(self):
        self.events = []
    def move(self, *p):
        self.events.append(('move', p))
    def button(self, down):
        self.events.append(('button', down))
    def scroll(self, steps):
        self.events.append(('scroll', steps))


def hand(fist):
    points = [P(x=.5, y=.5) for _ in range(21)]
    for tip, mcp in ((8,5), (12,9), (16,13), (20,17)):
        points[mcp] = P(x=.6, y=.5)
        points[tip] = P(x=.57 if fist else .9, y=.5)
    return points


def test_lost_hand_releases_drag_and_resets_smoothing():
    mouse = Mouse()
    control = GestureControl(mouse)
    control.update(hand(True))
    assert control.holding
    control.update(None)
    assert mouse.events[-1] == ('button', False)
    assert control.position is None
    assert not control.fist
    control.update(hand(False))
    assert not control.holding


def test_pause_releases_once_and_scroll_does_not_accumulate_while_dragging():
    mouse = Mouse()
    control = GestureControl(mouse)
    control.update(hand(True), scroll=True)
    control.release()
    control.release()
    assert [e for e in mouse.events if e[0] == 'button'] == [('button', True), ('button', False)]
    assert not any(e[0] == 'scroll' for e in mouse.events)
