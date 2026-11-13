# Hand Mouse

Kubuntu / KDE Plasma の Wayland セッションで、カメラに映した手を使ってマウスを操作する Python アプリです。MediaPipe で手の21点を推定し、Linux の `uinput` 仮想マウスへ入力を送ります。

![KDE版 Hand Mouse の画面。プレビューには個人のカメラ画像ではなく、手の骨格の説明図を表示しています。](docs/screenshot.png)

*画面例：開始・一時停止、カメラ選択、追従速度、任意のスクロール設定。画像内の手は説明用イラストです。実行中はここにカメラ映像と検出した骨格を表示します。*

## 起動

Python 3.11〜3.12 と [uv](https://docs.astral.sh/uv/) を使用します。依存ライブラリは `uv.lock` で管理しています。

```bash
cd ~/Projects/hand-mouse
uv sync --locked
uv run python main.py
```

「プレビュー開始」で映像を確認してから、「操作開始」を押してください。起動時は操作が無効です。認識とカメラ処理は別スレッドで実行し、UIから停止できます。カメラ映像は端末内で処理し、保存・送信しません。モデルがない場合のみ、Googleの公式配布先から初回ダウンロードします。

- 手を移動：カーソル移動。手のひらの中心を使用し、揺れを平滑化します。
- 握りこぶし：左ボタンを押し続ける。移動するとドラッグします。
- 手を開く：左ボタンを離す。
- 手を見失う：左ボタンを離し、判定状態をリセット。
- 映像が0.8秒以上途切れる：操作を一時停止。
- 「指の開閉でスクロール」：親指と人差し指の距離変化をホイールに変換。初期値は無効です。

画面内の `F8` で操作を切り替え、`Esc` で一時停止できます。これらはウィンドウ内のショートカットです。他のアプリを操作中は、システムトレイの「一時停止」、または次のコマンドを使ってください。

```bash
uv run python main.py --pause
```

KDEの「システム設定 → キーボード → ショートカット」でこのコマンドに任意のキーを割り当てることもできます。その際は `uv` と `main.py` を絶対パスで指定してください。同時起動は1プロセスに制限しています。通常の再起動コマンドは既存ウィンドウを表示します。

## Linux の入力権限

`/dev/uinput` への書き込み権限が必要です。アプリ自体は通常ユーザーで起動します。

```bash
sudo bash scripts/setup-uinput.sh
```

このスクリプトは `uinput` モジュールの起動時読み込みと、ローカルでログイン中のユーザーへ権限を渡す `uaccess` ルールを設定します。全ユーザーへの書き込み許可や `input` グループへの追加は行いません。`/dev/uinput` は仮想入力装置を作成するための権限です。

設定内容：

- `/etc/modules-load.d/hand-mouse.conf`
- `/etc/udev/rules.d/70-hand-mouse-uinput.rules`

削除する場合はこの2ファイルを削除し、udevルールを再読み込みしてログインし直してください。

## KDE のアプリメニュー

```bash
bash scripts/install-desktop.sh
```

「Hand Mouse」がアプリメニューに登録されます。デスクトップエントリーには「一時停止」アクションもあります。終了するとカメラ・仮想入力装置を解放します。自動起動は登録しません。

## カメラと画面

`--camera 2` で初期カメラ番号を指定できます。通常のRGBカメラとIRカメラ、映像を出さないメタデータ用デバイスが並ぶ場合があります。映像が出なければ別の番号を選び、プレビューを再開してください。

固定の1920×1080座標を廃止し、正規化した絶対座標をKWinに渡します。この環境では内蔵画面・倍率110%で確認済みです。複数画面での割り当てはKWin / libinputの扱いに従い、画面を指定する機能はありません。複数画面構成は未検証です。

## 開発・検証

```bash
uv run pytest -q
uv run python scripts/screenshot.py
```

握り操作、手を失った際のボタン解除、一時停止時の解除を自動テストしています。KDE Wayland上で実カメラ映像とMediaPipe推論を確認し、検証用Qtウィンドウで仮想マウスの移動・押下・ドラッグ・解放・ホイールイベントを実際に受信できることを確認しました。人が手を動かす一連の操作感、長時間の安定性、再起動後の動作は別途確認が必要です。

Windowsの `Mediapipe/apps/hand_mouse` から移行しました。元のWindows版コードと説明は `legacy/` に保存しています。KDE版は `pynput` やX11への依存をなくし、PySide6のGUIと仮想入力を使用します。Windows領域の元ファイルは移行元として残しています。Windows版を実行するための依存関係はこのプロジェクトには含めていません。

入力実装は [python-evdevの公式ドキュメント](https://python-evdev.readthedocs.io/en/stable/tutorial.html#injecting-input) に基づきます。MediaPipeモデルは [GoogleのHand Landmarkerモデル](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) を利用します。
