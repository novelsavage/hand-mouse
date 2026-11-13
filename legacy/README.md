## 手でマウス操作（OSレベル）

このアプリは「パン（移動）＝クリックホールド＋マウス移動」のように **マウス操作を分解**し、手のジェスチャで OS レベルのマウスイベントを送ります。

- **手の移動** → **カーソル移動**
- **握りこぶし（FIST）** → **左クリック押しっぱなし（ホールド）**
- **手を開く（OPEN）** → **左クリック解除**
- （任意）**親指＋人差し指の距離変化** → **マウスホイール（ズーム）**

## 実行

```bash
uv run python apps/hand_mouse/main.py
```

## 安全装置（重要）

- `ESC`: 即終了（キルスイッチ）
- `F8`: 有効/無効トグル（誤操作防止）
- `q`: カメラプレビューウィンドウ終了（OpenCV側）

## 画面プレビューでの表示

プレビューウィンドウに以下をリアルタイム表示します。

- 手ランドマーク **21点（キーポイント）** と **接続線（骨）**
- `Gesture: FIST/OPEN/NO HAND`
- `Mouse: HOLD/FREE`
- `curl_ratio idx/mid/ring/pinky=...`（握り判定の内部値）

## 判定ロジック（詳細）

### 1) カーソル移動（手の位置→画面座標）

- 入力: 手のランドマーク（正規化座標 \(0..1\)）
- 位置: **パーム中心**を使います（指先より安定）
  - パーム中心 \(C\) は `wrist(0), index_mcp(5), middle_mcp(9), ring_mcp(13), pinky_mcp(17)` の平均
- 端で暴れやすいので、`ROI_MARGIN` で外周をカットして画面全体にマッピングします
- 震え抑制として指数移動平均（EMA）で平滑化します（`SMOOTH_ALPHA`）

### 2) 握りこぶし（FIST）判定

「各指がどれだけ折りたたまれているか」を **距離比**で見ます（手の向きに比較的強い）。

- 対象指: 人差し指 / 中指 / 薬指 / 小指（4本）
- パーム中心 \(C\) を基準に、各指の
  - **tip**（先端）と
  - **mcp**（付け根）
  への距離比を計算します

\[
ratio = \frac{dist(C, tip)}{dist(C, mcp)}
\]

- 指が伸びているほど `ratio` は大きくなり、折りたたまれると小さくなります
- 4本のうち **一定本数以上が「折りたたまれた」**と判定されたら FIST とします

#### ヒステリシス（誤判定防止）

FIST の入り/抜けで閾値を変えます。

- **FISTに入る**: `ratio < CURL_ON` の指が `FIST_ON_COUNT` 本以上
- **FISTを維持**: `ratio < CURL_OFF` の指が `FIST_OFF_COUNT` 本より多い間は維持
  - `CURL_OFF` は `CURL_ON` より大きくして、チラつきを抑えます

### 3) クリックホールド（パンの分解）

- `FIST` になった瞬間に `mouse.left press`
- `OPEN` になった瞬間に `mouse.left release`
- カーソル移動は常に行うため、結果として「クリックホールド＋移動（ドラッグ）」になります

### 4) ズーム（任意）

- 親指 tip(4) と人差し指 tip(8) の距離の変化量をホイールに変換します
- `SCROLL_ENABLED=1` で有効（デフォルト有効）
- `SCROLL_HZ` で送出頻度を制限、`SCROLL_DEADZONE` で微小揺れを無視します

## 設定（環境変数）

### カメラ/画質/FPS（ベストエフォート）

```bash
set CAMERA_INDEX=0
set FRAME_WIDTH=640
set FRAME_HEIGHT=480
set FPS=30
```

### 精度・同時検出数

```bash
set NUM_HANDS=1
set MIN_HAND_DETECTION_CONFIDENCE=0.5
set MIN_HAND_PRESENCE_CONFIDENCE=0.5
set MIN_TRACKING_CONFIDENCE=0.5
```

### カーソルの滑らかさ/操作領域

```bash
set SMOOTH_ALPHA=0.25
set ROI_MARGIN=0.10
```

### 握り判定

```bash
set CURL_ON=1.12
set CURL_OFF=1.22
set FIST_ON_COUNT=3
set FIST_OFF_COUNT=1
```

### ズーム（ホイール）

```bash
set SCROLL_ENABLED=1
set DRAW_LANDMARKS=1
set SCROLL_DEADZONE=0.006
set SCROLL_GAIN=2200
set SCROLL_HZ=30
```

