#!/usr/bin/env bash
# Let a headless Claude Code session play FGO on its own with only the fgo MCP tools.
# usage: scripts/play.sh ["goal"]    log: logs/play-<time>.jsonl
set -euo pipefail
cd "$(dirname "$0")/.."

goal="${1:-Continue the main story from wherever the game is. Clear as many quests as you can.}"
mkdir -p logs
log="logs/play-$(date +%Y%m%d-%H%M%S).jsonl"

prompt="$goal

You are on your own: nobody will answer questions. Follow CLAUDE.md. Stop and say why when
the game needs something only the user should decide (spending Saint Quartz, summoning,
purchases, accepting terms, account or transfer screens), when AP and apples both run out,
or when you have been stuck on the same screen for a while. Apples are fine to use. End with a short report of what you
cleared and anything that went wrong with the tools."

echo "logging to $log"
# --tools "" removes every built-in tool (no shell, files, web, agents); only the fgo server's
# tools exist, and they are pre-approved.
set +e
claude -p "$prompt" \
  --tools "" \
  --mcp-config .mcp.json --strict-mcp-config \
  --allowedTools "mcp__fgo__*" \
  --output-format stream-json --verbose \
  > "$log" 2> "$log.stderr"
code=$?
set -e
echo "exit=$code log=$log"
exit $code
