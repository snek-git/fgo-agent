"""Follow a headless play log (stream-json) and print it as it happens."""

import json
import sys
import time
from pathlib import Path

LOGS = Path(__file__).resolve().parents[2] / "logs"

DIM, BOLD, RED, CYAN, YELLOW, RESET = "\033[2m", "\033[1m", "\033[31m", "\033[36m", "\033[33m", "\033[0m"


def follow(path: Path):
    with path.open() as f:
        while True:
            line = f.readline()
            if line:
                yield line
            else:
                time.sleep(0.3)


def show(event: dict) -> bool:
    """Print one event; True when the run has ended."""
    kind = event.get("type")
    if kind == "assistant":
        for part in event["message"]["content"]:
            if part["type"] == "text" and part["text"].strip():
                print(f"{BOLD}{part['text'].strip()}{RESET}")
            elif part["type"] == "tool_use":
                name = part["name"].removeprefix("mcp__fgo__")
                args = json.dumps(part["input"], ensure_ascii=False)
                print(f"{CYAN}> {name} {args if args != '{}' else ''}{RESET}")
    elif kind == "user" and isinstance(event["message"]["content"], list):
        for part in event["message"]["content"]:
            if part.get("type") != "tool_result":
                continue
            content = part["content"] if isinstance(part["content"], list) else [{"type": "text", "text": str(part["content"])}]
            for item in content:
                if item.get("type") != "text":
                    continue
                text = item["text"].replace("\n", " ")
                if text.startswith("[Image: source: "):
                    # the screenshot file Claude Code saved; open it to see what the agent saw
                    text = "[screenshot] " + text.removeprefix("[Image: source: ").rstrip("]")
                color = RED if part.get("is_error") else DIM
                print(f"{color}  {text}{RESET}")
    elif kind == "result":
        print(f"{YELLOW}=== {event.get('subtype')}: {event.get('num_turns')} turns, ${event.get('total_cost_usd')}{RESET}")
        if event.get("result"):
            print(event["result"])
        return True
    return False


def main(argv: list[str]) -> None:
    path = Path(argv[0]) if argv else max(LOGS.glob("play-*.jsonl"), key=lambda p: p.stat().st_mtime)
    print(f"{DIM}{path}{RESET}")
    for line in follow(path):
        try:
            if show(json.loads(line)):
                return
        except (json.JSONDecodeError, KeyError):
            continue


if __name__ == "__main__":
    main(sys.argv[1:])
