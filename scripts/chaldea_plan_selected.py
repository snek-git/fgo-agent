"""Plan max ascension and skills (and unlocked appends) in Chaldea for the servants marked 選択 in FGO.

FGO's select mark only exists in the game's own data, so it is read from the latest account
capture; Chaldea's import ignores it. Writes Chaldea's userdata.json, so Chaldea must be closed
(it would overwrite the file on its next save). A timestamped backup is written first.

usage: uv run python scripts/chaldea_plan_selected.py [--rarity 5] [--write]
"""

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from fgo_agent import account, atlas

USERDATA = Path.home() / ".local/opt/chaldea/userdata/user/userdata.json"
SELECTED = 16  # UserSvtStatusFlag.choice


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rarity", type=int, default=5)
    parser.add_argument("--write", action="store_true", help="without it, only show what would change")
    args = parser.parse_args()

    tables = json.loads(account.latest_capture().read_text())["cache"]["replaced"]
    servants = {s["id"]: s for s in atlas.servants()}
    selected = {servants[u["svtId"]]["collectionNo"]: servants[u["svtId"]]["name"]
                for u in tables["userSvt"] + tables.get("userSvtStorage", [])
                if u["svtId"] in servants and u["status"] & SELECTED and servants[u["svtId"]]["rarity"] == args.rarity}

    data = json.loads(USERDATA.read_text())
    user = data["users"][data["curUserKey"]]
    plan = user["plans"][user["curSvtPlanNo"]]
    changed = []
    for no, name in sorted(selected.items(), key=lambda kv: kv[1]):
        cur = user["servants"][str(no)]["cur"]
        target = plan["servants"].setdefault(str(no), json.loads(json.dumps(cur)) | {"favorite": False})
        target["ascension"] = max(target["ascension"], cur["ascension"], 4)
        target["skills"] = [max(t, c, 10) for t, c in zip(target["skills"], cur["skills"])]
        # Only appends already unlocked: unlocking costs servant coins the user may not want to spend
        target["appendSkills"] = [max(t, c, 10) if c > 0 else max(t, c)
                                  for t, c in zip(target["appendSkills"], cur["appendSkills"])]
        now = (cur["ascension"], cur["skills"], cur["appendSkills"])
        goal = (target["ascension"], target["skills"], target["appendSkills"])
        if goal != now:
            changed.append(f"#{no} {name}: asc {now[0]}->{goal[0]}, skills {now[1]}->{goal[1]}"
                           + (f", appends {now[2]}->{goal[2]}" if now[2] != goal[2] else ""))
    plan["title"] = plan["title"] or f"Max selected {args.rarity}*"

    print(f"{len(selected)} selected {args.rarity}* servants, {len(changed)} need something:")
    print("\n".join(changed))
    if not args.write:
        print("dry run: pass --write to save")
        return
    if subprocess.run(["pgrep", "-x", "chaldea"], capture_output=True).returncode == 0:
        raise SystemExit("Chaldea is running: close it first, or it overwrites this on its next save")
    backup = USERDATA.with_name(f"userdata.{time.strftime('%Y%m%d-%H%M%S')}.before-plan.json")
    shutil.copy2(USERDATA, backup)
    USERDATA.write_text(json.dumps(data, ensure_ascii=False))
    print(f"saved to {USERDATA} (backup: {backup.name})")


if __name__ == "__main__":
    main()
