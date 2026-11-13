import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlretrieve

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from pynput import keyboard, mouse


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return int(v)


def _env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return float(v)


def _get_screen_size() -> tuple[int, int]:
    # Windows優先。失敗したら保守的に 1920x1080 へフォールバック。
    try:
        import ctypes

        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    except Exception:
        return 1920, 1080


@dataclass
class MouseState:
    enabled: bool = True
    holding: bool = False
    last_scroll_time: float = 0.0
    pinch_ref: float | None = None
    fist: bool = False


def _ema(prev: float | None, cur: float, alpha: float) -> float:
    if prev is None:
        return cur
    return prev * (1.0 - alpha) + cur * alpha


HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
)


def _draw_hand_skeleton(frame_bgr, hand_landmarks, *, color=(0, 255, 0)) -> None:
    h, w = frame_bgr.shape[:2]
    pts: list[tuple[int, int]] = []
    for lm in hand_landmarks:
        pts.append((int(lm.x * w), int(lm.y * h)))

    for a, b in HAND_CONNECTIONS:
        cv2.line(frame_bgr, pts[a], pts[b], color, 2, cv2.LINE_AA)

    for x, y in pts:
        cv2.circle(frame_bgr, (x, y), 3, (0, 0, 255), -1, cv2.LINE_AA)


def main() -> None:
    camera_index = _env_int("CAMERA_INDEX", 0)

    # Camera properties (best-effort)
    frame_width = _env_int("FRAME_WIDTH", 640)
    frame_height = _env_int("FRAME_HEIGHT", 480)
    target_fps = _env_int("FPS", 30)

    # Hand landmarker model
    model_path = Path(os.environ.get("HAND_LANDMARKER_TASK", "models/hand_landmarker.task"))
    model_url = os.environ.get(
        "HAND_LANDMARKER_TASK_URL",
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    )

    # Control tuning
    alpha = _env_float("SMOOTH_ALPHA", 0.25)  # 0..1 (larger = less smoothing)
    roi_margin = _env_float("ROI_MARGIN", 0.10)  # crop outside [m,1-m] to avoid edges
    scroll_enabled = _env_int("SCROLL_ENABLED", 0)  # 1: enable zoom by pinch distance
    draw_landmarks = _env_int("DRAW_LANDMARKS", 1)  # 1: draw keypoints & bones on preview
    scroll_deadzone = _env_float("SCROLL_DEADZONE", 0.006)
    scroll_gain = _env_float("SCROLL_GAIN", 2200.0)  # pinch delta -> wheel units
    scroll_hz = _env_float("SCROLL_HZ", 30.0)  # rate limit

    # Fist (grab) detection: finger curl ratio thresholds + hysteresis
    curl_on = _env_float("CURL_ON", 1.12)
    curl_off = _env_float("CURL_OFF", 1.22)
    fist_on_count = _env_int("FIST_ON_COUNT", 3)  # how many fingers must be curled
    fist_off_count = _env_int("FIST_OFF_COUNT", 1)  # how many curled allowed to keep fist

    num_hands = _env_int("NUM_HANDS", 1)
    min_hand_detection_confidence = _env_float("MIN_HAND_DETECTION_CONFIDENCE", 0.5)
    min_hand_presence_confidence = _env_float("MIN_HAND_PRESENCE_CONFIDENCE", 0.5)
    min_tracking_confidence = _env_float("MIN_TRACKING_CONFIDENCE", 0.5)

    if curl_off <= curl_on:
        raise ValueError("CURL_OFF は CURL_ON より大きくしてください（ヒステリシス用）")

    if not model_path.exists():
        model_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"モデルをダウンロードします: {model_url}")
        urlretrieve(model_url, model_path)
        print(f"保存しました: {model_path}")

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"カメラを開けませんでした (CAMERA_INDEX={camera_index})")
    if frame_width > 0:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
    if frame_height > 0:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
    if target_fps > 0:
        cap.set(cv2.CAP_PROP_FPS, target_fps)

    screen_w, screen_h = _get_screen_size()
    m = mouse.Controller()

    stop_flag = {"stop": False}

    def on_press(key):
        if key == keyboard.Key.esc:
            stop_flag["stop"] = True
            return False
        if key == keyboard.Key.f8:
            state.enabled = not state.enabled

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    state = MouseState()
    x_f: float | None = None
    y_f: float | None = None

    base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
    options = mp_vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=num_hands,
        min_hand_detection_confidence=min_hand_detection_confidence,
        min_hand_presence_confidence=min_hand_presence_confidence,
        min_tracking_confidence=min_tracking_confidence,
        running_mode=mp_vision.RunningMode.IMAGE,
    )

    def clamp01(v: float) -> float:
        return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v

    def dist(a, b) -> float:
        dx = a.x - b.x
        dy = a.y - b.y
        return (dx * dx + dy * dy) ** 0.5

    def palm_center(hand):
        xs = [hand[i].x for i in (0, 5, 9, 13, 17)]
        ys = [hand[i].y for i in (0, 5, 9, 13, 17)]
        return sum(xs) / len(xs), sum(ys) / len(ys)

    def finger_curl_ratio(hand, tip_i: int, mcp_i: int) -> float:
        # ratio = dist(palm_center, tip) / dist(palm_center, mcp)
        cx, cy = palm_center(hand)

        class P:
            def __init__(self, x: float, y: float):
                self.x = x
                self.y = y

        c = P(cx, cy)
        tip = hand[tip_i]
        mcp = hand[mcp_i]
        d_tip = dist(c, tip)
        d_mcp = dist(c, mcp)
        if d_mcp <= 1e-6:
            return 999.0
        return d_tip / d_mcp

    with mp_vision.HandLandmarker.create_from_options(options) as landmarker:
        while not stop_flag["stop"]:
            ok, frame = cap.read()
            if not ok:
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_image)

            # Show camera preview for debugging
            status = "ENABLED" if state.enabled else "DISABLED"
            cv2.putText(
                frame,
                f"Hand Mouse [{status}]  ESC:quit  F8:toggle",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            ratios_txt = ""
            gesture_txt = "NO HAND"

            if result.hand_landmarks and state.enabled:
                if draw_landmarks:
                    for i, hand_lm in enumerate(result.hand_landmarks):
                        _draw_hand_skeleton(
                            frame,
                            hand_lm,
                            color=(0, 255, 0) if i == 0 else (160, 160, 160),
                        )

                # Use first hand only for minimal control.
                hand = result.hand_landmarks[0]

                # Use palm center for cursor (more stable than a fingertip)
                px, py = palm_center(hand)

                # Pinch uses index tip & thumb tip (normalized 0..1)
                ix, iy = hand[8].x, hand[8].y
                tx, ty = hand[4].x, hand[4].y

                # Fist detection (index/middle/ring/pinky)
                r_index = finger_curl_ratio(hand, 8, 5)
                r_middle = finger_curl_ratio(hand, 12, 9)
                r_ring = finger_curl_ratio(hand, 16, 13)
                r_pinky = finger_curl_ratio(hand, 20, 17)
                ratios = [r_index, r_middle, r_ring, r_pinky]
                curled_on = sum(1 for r in ratios if r < curl_on)
                curled_off = sum(1 for r in ratios if r < curl_off)

                # Hysteresis: enter fist by strict threshold, exit by looser threshold
                if not state.fist:
                    state.fist = curled_on >= fist_on_count
                else:
                    state.fist = curled_off > fist_off_count

                gesture_txt = "FIST" if state.fist else "OPEN"
                ratios_txt = (
                    f"curl_ratio idx/mid/ring/pinky="
                    f"{r_index:.2f}/{r_middle:.2f}/{r_ring:.2f}/{r_pinky:.2f}"
                )

                # Cursor mapping with margin crop
                px = (clamp01(px) - roi_margin) / (1.0 - 2.0 * roi_margin)
                py = (clamp01(py) - roi_margin) / (1.0 - 2.0 * roi_margin)
                px = clamp01(px)
                py = clamp01(py)

                x_px = px * (screen_w - 1)
                y_px = py * (screen_h - 1)

                x_f = _ema(x_f, x_px, alpha)
                y_f = _ema(y_f, y_px, alpha)
                m.position = (int(x_f), int(y_f))

                # Hold = left button down (pan decomposed to click-hold + move)
                if state.fist and not state.holding:
                    m.press(mouse.Button.left)
                    state.holding = True
                elif (not state.fist) and state.holding:
                    m.release(mouse.Button.left)
                    state.holding = False

                # Zoom by wheel using pinch distance (optional; rate-limited)
                if scroll_enabled:
                    pinch_dist = ((ix - tx) ** 2 + (iy - ty) ** 2) ** 0.5
                    if state.pinch_ref is None:
                        state.pinch_ref = pinch_dist
                    now = time.time()
                    if now - state.last_scroll_time >= (1.0 / max(scroll_hz, 1.0)):
                        delta = pinch_dist - state.pinch_ref
                        if abs(delta) >= scroll_deadzone:
                            wheel = int(delta * scroll_gain)
                            if wheel != 0:
                                m.scroll(0, wheel)
                                state.last_scroll_time = now
                        state.pinch_ref = pinch_dist

            else:
                # Safety: if hand is lost while holding, release.
                if state.holding:
                    m.release(mouse.Button.left)
                    state.holding = False
                state.pinch_ref = None
                state.fist = False

            # Overlay gesture state
            hold_txt = "HOLD" if state.holding else "FREE"
            cv2.putText(
                frame,
                f"Gesture: {gesture_txt}   Mouse: {hold_txt}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0) if state.holding else (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            if ratios_txt:
                cv2.putText(
                    frame,
                    ratios_txt,
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

            cv2.imshow("Hand Mouse", frame)
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                break

    if state.holding:
        m.release(mouse.Button.left)
    cap.release()
    cv2.destroyAllWindows()
    listener.stop()


if __name__ == "__main__":
    main()
