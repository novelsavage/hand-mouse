#!/usr/bin/env bash
# Grant /dev/uinput only to the active local desktop user using logind ACLs.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo '実行方法: sudo bash scripts/setup-uinput.sh' >&2
  exit 1
fi
printf 'uinput\n' > /etc/modules-load.d/hand-mouse.conf
printf 'SUBSYSTEM=="misc", KERNEL=="uinput", TAG+="uaccess", OPTIONS+="static_node=uinput"\n' > /etc/udev/rules.d/70-hand-mouse-uinput.rules
modprobe uinput
udevadm control --reload-rules
udevadm trigger --action=change /sys/class/misc/uinput
udevadm settle
echo '設定しました。アプリ本体は通常ユーザーで起動してください。'
