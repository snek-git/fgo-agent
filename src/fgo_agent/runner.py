"""Work through the task queue: one headless agent session per task, then one account sync.

Runs as the user service fgo-agent-queue (started from the board), so it keeps going if the
board, the app or Claude Code closes. Stop it with `systemctl --user stop fgo-agent-queue`.
"""

import json
import subprocess
import time

from . import tasks
from .memory import DATA

PROJECT = DATA.parent


def _result(log: str) -> dict:
    """The run's final result record (cost, turns) from its stream-json log."""
    try:
        for line in reversed((PROJECT / log).read_text().splitlines()):
            entry = json.loads(line)
            if entry.get("type") == "result":
                return {"cost": entry.get("total_cost_usd"), "turns": entry.get("num_turns"),
                        "report": entry.get("result")}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def run_task(task: dict) -> None:
    tasks.update(task["id"], status="running", started=time.time())
    proc = subprocess.run(["scripts/play.sh", "-b", "-k", tasks.prompt(task)], cwd=PROJECT,
                          capture_output=True, text=True)
    log = next((line.split("logging to ")[1].split(" ")[0] for line in proc.stdout.splitlines()
                if line.startswith("logging to ")), None)
    tasks.update(task["id"], status="done" if proc.returncode == 0 else "failed", finished=time.time(),
                 exit=proc.returncode, log=log, error=proc.stderr[-2000:] or None, **(_result(log) if log else {}))


def main() -> None:
    if tasks.unit_active(tasks.AGENT_UNIT):
        raise SystemExit(f"{tasks.AGENT_UNIT} is playing: one session per account, so the queue waits")
    ran = False
    while (task := next((t for t in tasks.load() if t["status"] == "queued"), None)):
        run_task(task)
        ran = True
    if ran:
        # One sync at the end, not per task: each capture restarts FGO
        subprocess.run(["scripts/capture-account.sh"], cwd=PROJECT)
    if subprocess.run(["pgrep", "-x", "scrcpy"], capture_output=True).returncode != 0:
        subprocess.run(["scripts/emu.sh", "down"], cwd=PROJECT)
