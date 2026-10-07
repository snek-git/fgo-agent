#!/usr/bin/env bash
# Play FGO yourself: start the emulator if needed, open the game, show it in a scrcpy window.
# If an agent session is playing, the window opens view-only so you don't fight over taps.
set -uo pipefail

SERIAL=127.0.0.1:5555
PKG=com.aniplex.fategrandorder
TITLE="Fate/Grand Order"
PROJECT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
LOG="$HOME/.cache/fgo-agent/launcher.log"
mkdir -p "$(dirname "$LOG")"
exec 2>>"$LOG"
echo "--- $(date) launch" >&2

fail() {
  echo "error: $1" >&2
  notify-send -a "$TITLE" -i "$PROJECT/app/fgo.png" "$TITLE" "$1 (log: $LOG)" || true
  exit 1
}

# Already open: just focus it
if pgrep -f "scrcpy.*--window-title=$TITLE" >/dev/null; then
  command -v hyprctl >/dev/null && hyprctl dispatch focuswindow "title:^$TITLE\$" >/dev/null
  exit 0
fi

# Emulator
if [ "$(docker inspect -f '{{.State.Running}}' fgo-redroid 2>>"$LOG")" != "true" ]; then
  notify-send -a "$TITLE" -i "$PROJECT/app/fgo.png" "$TITLE" "Starting the emulator..." || true
  docker compose -f "$PROJECT/emu/compose.yaml" up -d >&2 || fail "could not start the emulator container"
fi
for _ in $(seq 1 60); do
  [ "$(docker exec fgo-redroid getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] && break
  sleep 2
done
[ "$(docker exec fgo-redroid getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] \
  || fail "the emulator did not finish booting"
adb connect "$SERIAL" >&2 || fail "adb could not connect to $SERIAL"

# Game
if [ -z "$(adb -s "$SERIAL" shell pidof "$PKG" 2>>"$LOG" | tr -d '\r')" ]; then
  adb -s "$SERIAL" shell am start -n "$PKG/jp.delightworks.Fgo.player.AndroidPlugin" >&2 \
    || fail "could not start FGO"
fi

# An agent session (scripts/play.sh) owns the input while it runs
control=()
if pgrep -f "claude.*--strict-mcp-config" >/dev/null; then
  control=(--no-control)
  notify-send -a "$TITLE" -i "$PROJECT/app/fgo.png" "$TITLE" \
    "The agent is playing, so this window is view-only. Stop the agent to play yourself." || true
fi

# The image has no opus encoder, so audio goes over aac
exec scrcpy -s "$SERIAL" --window-title="$TITLE" --audio-codec=aac --max-fps=60 \
  --disable-screensaver "${control[@]}" 2>>"$LOG"
