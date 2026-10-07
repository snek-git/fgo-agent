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
the game needs something only the user should decide (spending Saint Quartz or apples,
summoning, purchases, accepting terms, account or transfer screens), when AP runs out, or
when you have been stuck on the same screen for a while. End with a short report of what you
cleared and anything that went wrong with the tools."

echo "logging to $log"
claude -p "$prompt" \
  --mcp-config .mcp.json --strict-mcp-config \
  --allowedTools "mcp__fgo__*" \
  --disallowedTools "Bash" "Edit" "Write" "NotebookEdit" "WebFetch" "WebSearch" "Agent" \
  --output-format stream-json --verbose \
  > "$log"
echo "exit=$? log=$log"
