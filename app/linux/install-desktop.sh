#!/bin/sh
# Puts puritty in the desktop's menu and dock for this user (docs/windows.md
# WS25): its icon in ~/.local/share/icons/hicolor at each size, and
# puritty.desktop in ~/.local/share/applications with Exec naming this
# checkout's app/puritty. Run again after moving the checkout; nothing
# else is touched, and removing those files undoes it.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
app="$(cd "$here/.." && pwd)/puritty"
data="${XDG_DATA_HOME:-$HOME/.local/share}"
for s in 16 24 32 48 64 256; do
    mkdir -p "$data/icons/hicolor/${s}x${s}/apps"
    cp "$here/../icon/png/$s.png" "$data/icons/hicolor/${s}x${s}/apps/puritty.png"
done
mkdir -p "$data/icons/hicolor/scalable/apps"
cp "$here/../icon/puritty.svg" "$data/icons/hicolor/scalable/apps/puritty.svg"
mkdir -p "$data/applications"
sed "s|^Exec=puritty|Exec=$app|" "$here/puritty.desktop" > "$data/applications/puritty.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$data/applications" || true
echo "puritty.desktop and its icons are in $data"
