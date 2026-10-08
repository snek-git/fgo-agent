"""The task queue the board fills and the runner works through, one task at a time.

One emulator and one account means one agent session at a time (a second login kicks the
first out), so this is a queue, not a pool. data/queue.json holds it so the board, the desktop
app and the runner all see the same thing.
"""

import json
import subprocess
import time
import uuid

from . import memory

QUEUE = memory.DATA / "queue.json"
RUNNER_UNIT = "fgo-agent-queue"
AGENT_UNIT = "fgo-agent-run"
SYNC_UNIT = "fgo-agent-sync"

RULES = """Rules: apples (gold, silver, bronze) may be used for AP{apples}. Never spend Saint Quartz,
never summon, never buy anything. Command spells only as a last resort. Call game tools one at a
time. Write what you learn in notes. End with a short report: what you did, what is left, why."""

PROMPTS = {
    "quests": """Clear these quests, in this order:
{quest_list}
For each: find it in the game (interludes: 幕間の物語, strengthening: 強化クエスト, or the servant's own
entry), check find_quest + prepare_battle, read the party restriction, build a party with fitting
CEs (roster, list_ces, find_owned) and clear it. Skip one with a hard gimmick after one failed try
and say why.""",
    "story": """Clear the uncleared quests of 「{war_name}」 (war {war}): first the main story quests, then
the free quests (each pays Saint Quartz on its first clear). Quests:
{quest_list}""",
    "farm": """Farm {item}: collect {count} more of it.
1. Pick the free quest with the best drop rate for it that you can clear in 3 turns (one wave per
   turn). Check its enemies with find_quest + prepare_battle.
2. Exploratory runs: find a party, support and turn plan that clears it in exactly 3 turns. Try at
   most 3 runs. Write the plan with save_farm_plan (party, support, FGA skill command per wave).
3. Then farm it with farm_battle(skill_command): start each run yourself (pick the plan's
   support; after the first run FGA's Repeat brings you back to support select), and FGA plays
   the battle. Keep going until you have {count} more, or the apple budget is spent.
If no 3-turn plan works, farm with the best plan you found and say how many turns it takes.""",
    "custom": "{text}",
}


def load() -> list[dict]:
    return json.loads(QUEUE.read_text()) if QUEUE.exists() else []


def save(tasks: list[dict]) -> None:
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE.with_suffix(".tmp")
    tmp.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(QUEUE)


def add(kind: str, title: str, payload: dict, apples: int | None = None) -> dict:
    if kind not in PROMPTS:
        raise ValueError(f"unknown task kind {kind!r}; one of {', '.join(PROMPTS)}")
    task = {"id": uuid.uuid4().hex[:8], "kind": kind, "title": title, "payload": payload,
            "apples": apples, "status": "queued", "created": time.time()}
    save(load() + [task])
    return task


def remove(task_id: str) -> None:
    save([t for t in load() if t["id"] != task_id or t["status"] == "running"])


def retry(task_id: str) -> None:
    """Put a stopped or failed order back in line; the next run starts it in a fresh session."""
    save([t | {"status": "queued"} if t["id"] == task_id and t["status"] in ("stopped", "failed") else t for t in load()])


def update(task_id: str, **fields) -> None:
    save([t | fields if t["id"] == task_id else t for t in load()])


def prompt(task: dict) -> str:
    payload = dict(task["payload"])
    if "quests" in payload:
        payload["quest_list"] = "\n".join(f"- {q['name']} (quest {q['quest_id']}{', ' + q['who'] if q.get('who') else ''})"
                                          for q in payload["quests"])
    apples = "" if task.get("apples") is None else f", at most {task['apples']} apples in this task"
    return PROMPTS[task["kind"]].format(**payload) + "\n\n" + RULES.format(apples=apples)


def unit_active(unit: str) -> bool:
    return subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit]).returncode == 0


def state() -> dict:
    return {"tasks": load(), "runner": unit_active(RUNNER_UNIT), "agent": unit_active(AGENT_UNIT),
            "syncing": unit_active(SYNC_UNIT)}
