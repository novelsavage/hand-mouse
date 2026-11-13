#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
uv_path=$(command -v uv)
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/hand-mouse.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Hand Mouse
Comment=手のジェスチャでマウス操作
Exec="$uv_path" run --project "$project_dir" python "$project_dir/main.py"
Path=$project_dir
Icon=input-mouse
Terminal=false
Categories=Utility;Accessibility;
StartupNotify=true
Actions=Pause;

[Desktop Action Pause]
Name=一時停止
Exec="$uv_path" run --project "$project_dir" python "$project_dir/main.py" --pause
DESKTOP
cat > "$HOME/.local/share/applications/hand-gallery.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Hand Gallery
Comment=手で作品をめくるデジタル展示
Exec="$uv_path" run --project "$project_dir" python "$project_dir/gallery.py"
Path=$project_dir
Icon=image-x-generic
Terminal=false
Categories=Graphics;
StartupNotify=true
DESKTOP
command -v update-desktop-database >/dev/null && update-desktop-database "$HOME/.local/share/applications"
