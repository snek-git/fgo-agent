#!/usr/bin/env bash
# Install the FGO launcher: a `fgo` command and an app entry (Walker, rofi, any menu).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

chmod +x "$here/fgo.sh"
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
ln -sf "$here/fgo.sh" "$HOME/.local/bin/fgo"

cat > "$HOME/.local/share/applications/fate-grand-order.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Fate/Grand Order
GenericName=FGO (emulator)
Comment=Play FGO JP in the redroid emulator
Exec=$here/fgo.sh
Icon=$here/fgo.png
Terminal=false
Categories=Game;
Keywords=fgo;fate;grand;order;
StartupWMClass=scrcpy
EOF

project="$(dirname "$here")"
cat > "$HOME/.local/share/applications/chaldea-terminal.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Chaldea Terminal
GenericName=FGO account board
Comment=What is left on your FGO account, and orders for the agent
Exec=uv run --project $project --extra app fgo-agent app
Path=$project
Icon=$here/chaldea-terminal.svg
Terminal=false
Categories=Game;
Keywords=fgo;chaldea;board;agent;
StartupWMClass=chaldea-terminal
EOF

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "installed: fgo command, Fate/Grand Order and Chaldea Terminal app entries"
