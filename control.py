"""Gesture state machine and Wayland-compatible Linux input device."""
import math


class GestureControl:
    def __init__(self, mouse):
        self.mouse = mouse
        self.holding = False
        self.fist = False
        self.position = None
        self.pinch = None

    def release(self):
        if self.holding:
            self.mouse.button(False)
        self.holding = self.fist = False
        self.position = self.pinch = None

    def update(self, hand, alpha=0.25, margin=0.1, scroll=False):
        if not hand:
            self.release()
            return "手を検出していません"
        cx = sum(hand[i].x for i in (0, 5, 9, 13, 17)) / 5
        cy = sum(hand[i].y for i in (0, 5, 9, 13, 17)) / 5
        ratios = [math.hypot(hand[t].x-cx, hand[t].y-cy) /
                  max(1e-6, math.hypot(hand[m].x-cx, hand[m].y-cy))
                  for t, m in ((8, 5), (12, 9), (16, 13), (20, 17))]
        self.fist = (sum(r < 1.22 for r in ratios) > 1 if self.fist
                     else sum(r < 1.12 for r in ratios) >= 3)
        point = tuple(max(0, min(1, (v-margin)/(1-2*margin))) for v in (cx, cy))
        if self.position:
            point = tuple(p*(1-alpha)+v*alpha for p, v in zip(self.position, point))
        self.position = point
        self.mouse.move(*point)
        if self.fist != self.holding:
            self.mouse.button(self.fist)
            self.holding = self.fist
        pinch = math.hypot(hand[8].x-hand[4].x, hand[8].y-hand[4].y)
        if scroll and not self.fist and self.pinch is not None:
            delta = pinch-self.pinch
            if abs(delta) > 0.012:
                self.mouse.scroll(1 if delta > 0 else -1)
                self.pinch = pinch
        else:
            self.pinch = pinch
        return "握りこぶし · ドラッグ中" if self.fist else "手を開く · カーソル移動"


class LinuxMouse:
    def __init__(self):
        from evdev import UInput, AbsInfo, ecodes as e
        self.e = e
        self.device = UInput({e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT],
                              e.EV_ABS: [(e.ABS_X, AbsInfo(0, 0, 32767, 0, 0, 0)),
                                         (e.ABS_Y, AbsInfo(0, 0, 32767, 0, 0, 0))],
                              e.EV_REL: [e.REL_WHEEL]}, name="Hand Mouse", version=1)

    def move(self, x, y):
        self.device.write(self.e.EV_ABS, self.e.ABS_X, round(x*32767))
        self.device.write(self.e.EV_ABS, self.e.ABS_Y, round(y*32767))
        self.device.syn()

    def button(self, pressed):
        self.device.write(self.e.EV_KEY, self.e.BTN_LEFT, int(pressed))
        self.device.syn()

    def scroll(self, steps):
        self.device.write(self.e.EV_REL, self.e.REL_WHEEL, steps)
        self.device.syn()

    def close(self):
        self.button(False)
        self.device.close()
