#!/usr/bin/env bash
# Play FGO yourself: start the emulator if needed, open the game, show it in a scrcpy window.
# If an agent session is playing, the window opens view-only so you don't fight over taps.
# Closing the window closes FGO and stops the emulator, so the game never sits logged in
# around the clock; an agent run keeps both running.
set -uo pipefail

SERIAL=127.0.0.1:5555
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

# Emulator and game
if [ "$(docker inspect -f '{{.State.Running}}' fgo-redroid 2>>"$LOG")" != "true" ]; then
  notify-send -a "$TITLE" -i "$PROJECT/app/fgo.png" "$TITLE" "Starting the emulator..." || true
fi
"$PROJECT/scripts/emu.sh" up || fail "could not start the emulator or FGO"

# An agent session (scripts/play.sh) owns the input while it runs
agent_running() { pgrep -f "claude.*--strict-mcp-config" >/dev/null; }
control=()
if agent_running; then
  control=(--no-control)
  notify-send -a "$TITLE" -i "$PROJECT/app/fgo.png" "$TITLE" \
    "The agent is playing, so this window is view-only. Stop the agent to play yourself." || true
fi

# The image has no opus encoder, so audio goes over aac
scrcpy -s "$SERIAL" --window-title="$TITLE" --audio-codec=aac --max-fps=60 \
  --disable-screensaver "${control[@]}" 2>>"$LOG"
echo "window closed (scrcpy exit $?)" >&2

if agent_running; then
  echo "agent still playing: leaving FGO and the emulator running" >&2
  exit 0
fi
"$PROJECT/scripts/emu.sh" down && echo "FGO closed, emulator stopped" >&2
