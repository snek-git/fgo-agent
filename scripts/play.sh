#!/usr/bin/env bash
# Let Claude Code play FGO with only the fgo MCP tools.
# usage: scripts/play.sh ["goal"]        interactive: watch it live, interrupt with Esc
#        scripts/play.sh -b ["goal"]     headless: logs to logs/play-<time>.jsonl,
#                                        follow it with `uv run fgo-agent watch`
#        scripts/play.sh -d ["goal"]     headless as the user service fgo-agent-run, so it
#                                        keeps going if the terminal or Claude Code closes;
#                                        stop it with `systemctl --user stop fgo-agent-run`
#        add -r <session> to resume a session that stopped, with the goal as the message
#        add -k to keep the emulator running afterwards (the task queue runs several in a row)
# The emulator and FGO start if they are not running, and stop again after the run unless the
# FGO window (app/fgo.sh) is open.
set -euo pipefail
cd "$(dirname "$0")/.."

background=false
detach=false
keep=false
resume=()
while [ $# -gt 0 ]; do
  case "$1" in
    -b) background=true; shift ;;
    -d) detach=true; shift ;;
    -k) keep=true; shift ;;
    -r) resume=(--resume "$2"); shift 2 ;;
    *) break ;;
  esac
done
goal="${1:-Continue the main story from wherever the game is. Clear as many quests as you can.}"

if $detach; then
  systemd-run --user --unit=fgo-agent-run --collect --working-directory="$PWD" \
    --setenv=PATH="$PATH" --setenv=HOME="$HOME" \
    scripts/play.sh -b "${resume[@]/#--resume/-r}" "$goal"
  echo "running as fgo-agent-run; follow it with: uv run fgo-agent watch"
  exit 0
fi

if [ ${#resume[@]} -gt 0 ]; then
  prompt="$goal"
else
  prompt="$goal

You are on your own: nobody will answer questions. Follow CLAUDE.md. Stop and say why when
the game needs something only the user should decide (spending Saint Quartz, summoning,
purchases, accepting terms, account or transfer screens), when AP and apples both run out,
or when you have been stuck on the same screen for a while. Apples are fine to use. Command
spells are a last resort, and a clear that needed them does not count as a success. End with
a short report of what you cleared, what it cost, and anything that went wrong with the tools."
fi

scripts/emu.sh up
stop_emulator() {
  # Leave it running when the user has the game window open
  if pgrep -x scrcpy > /dev/null; then
    echo "FGO window open: leaving the emulator running"
  else
    scripts/emu.sh down && echo "emulator stopped"
  fi
}
$keep || trap stop_emulator EXIT

# --tools "" removes every built-in tool (no shell, files, web, agents); only the fgo server's
# tools exist, and they are pre-approved.
flags=(--tools "" --mcp-config .mcp.json --strict-mcp-config --allowedTools "mcp__fgo__*" "${resume[@]}")

if ! $background; then
  claude "${flags[@]}" "$prompt"
  exit $?
fi

mkdir -p logs
log="logs/play-$(date +%Y%m%d-%H%M%S).jsonl"
echo "logging to $log (follow with: uv run fgo-agent watch)"
set +e
claude -p "$prompt" "${flags[@]}" --output-format stream-json --verbose > "$log" 2> "$log.stderr"
code=$?
set -e
echo "exit=$code log=$log"
exit $code
