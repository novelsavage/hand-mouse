"""Camera-independent, timestamp-based exhibition page gesture recognizer."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SwipeResult:
    page: int = 0  # +1 next, -1 previous
    message: str = "開いた手を中央の枠に合わせてください"
    progress: float = 0.0
    x: float | None = None
    y: float | None = None


class PageGesture:
    def __init__(self, dwell=.10, distance=.10, cooldown=.55, max_duration=2.5):
        self.dwell = dwell
        self.distance = distance
        self.cooldown = cooldown
        self.max_duration = max_duration
        self.reset()

    def reset(self):
        self.center_since = None
        self.anchor = None
        self.started = None
        self.locked_until = 0.0

    def update(self, hand, now):
        if not hand:
            self.center_since = self.anchor = self.started = None
            return SwipeResult(message="手をカメラに向けて開いてください")
        x = sum(hand[i].x for i in (0,5,9,13,17))/5
        y = sum(hand[i].y for i in (0,5,9,13,17))/5
        wrist = hand[0]
        def distance(i):
            return math.hypot(hand[i].x-wrist.x, hand[i].y-wrist.y)
        open_fingers = sum(distance(t) > 1.06*distance(p)
                           for t,p in ((8,6),(12,10),(16,14),(20,18)))
        if open_fingers < 2:
            self.center_since = self.anchor = self.started = None
            return SwipeResult(message="手を開いてください", x=x, y=y)
        if now < self.locked_until:
            self.center_since = None
            return SwipeResult(message="切り替えました · 手を中央へ戻してください", x=x, y=y)
        if self.anchor is None:
            if .15 <= x <= .85 and .08 <= y <= .92:
                if self.center_since is None:
                    self.center_since = now
                progress = min(1, (now-self.center_since)/self.dwell)
                if progress >= 1:
                    self.anchor = (x,y)
                return SwipeResult(message="そのまま少し止めてください" if progress < 1 else "← 左へ払うと次の作品 / 右へ払うと前の作品 →",
                                   progress=progress, x=x, y=y)
            self.center_since = None
            return SwipeResult(x=x, y=y)
        dx, dy = x-self.anchor[0], y-self.anchor[1]
        if abs(dy) > .35:
            self.center_since = self.anchor = self.started = None
            return SwipeResult(message="中央に戻して、横に動かしてください", x=x, y=y)
        if abs(dx) > .04 and self.started is None:
            self.started = now
        if self.started is not None and now-self.started > self.max_duration:
            self.center_since = self.anchor = self.started = None
            return SwipeResult(message="中央から、手を横に払ってください", x=x, y=y)
        if abs(dx) >= self.distance:
            page = 1 if dx < 0 else -1
            self.center_since = self.anchor = self.started = None
            self.locked_until = now+self.cooldown
            return SwipeResult(page=page, message="次の作品" if page == 1 else "前の作品", x=x, y=y)
        return SwipeResult(message="← 左へ払うと次の作品 / 右へ払うと前の作品 →", progress=1, x=x, y=y)
