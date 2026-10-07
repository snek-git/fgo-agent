#!/usr/bin/env bash
# Let Claude Code play FGO with only the fgo MCP tools.
# usage: scripts/play.sh ["goal"]        interactive: watch it live, interrupt with Esc
#        scripts/play.sh -b ["goal"]     headless: logs to logs/play-<time>.jsonl,
#                                        follow it with `uv run fgo-agent watch`
set -euo pipefail
cd "$(dirname "$0")/.."

background=false
if [ "${1:-}" = "-b" ]; then
  background=true
  shift
fi
goal="${1:-Continue the main story from wherever the game is. Clear as many quests as you can.}"

prompt="$goal

You are on your own: nobody will answer questions. Follow CLAUDE.md. Stop and say why when
the game needs something only the user should decide (spending Saint Quartz, summoning,
purchases, accepting terms, account or transfer screens), when AP and apples both run out,
or when you have been stuck on the same screen for a while. Apples are fine to use. Command
spells are a last resort, and a clear that needed them does not count as a success. End with
a short report of what you cleared, what it cost, and anything that went wrong with the tools."

# --tools "" removes every built-in tool (no shell, files, web, agents); only the fgo server's
# tools exist, and they are pre-approved.
flags=(--tools "" --mcp-config .mcp.json --strict-mcp-config --allowedTools "mcp__fgo__*")

if ! $background; then
  exec claude "${flags[@]}" "$prompt"
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
