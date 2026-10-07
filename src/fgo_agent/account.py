"""Fill the roster and CE list from a captured login response (scripts/capture-account.sh).

The login response holds the whole account. Servants and CEs are both "userSvt" units, told
apart by their svtId in Atlas's exports. Notes and NP versions the agent recorded by hand are
kept; everything else is replaced by what the game says.
"""

import json
import time
from pathlib import Path

from . import atlas, memory

CAPTURES = memory.DATA / "capture"


def latest_capture() -> Path:
    files = sorted(CAPTURES.glob("login-top-*.bin"))
    if not files:
        raise FileNotFoundError("no capture yet: run scripts/capture-account.sh")
    return files[-1]


def import_capture(path: Path) -> str:
    tables = json.loads(path.read_text())["cache"]["replaced"]
    units = tables["userSvt"] + tables.get("userSvtStorage", [])
    servants = {s["id"]: s for s in atlas.servants()}
    equips = {c["id"]: c for c in atlas.craft_essences()}
    bond = {c["svtId"]: c["friendshipRank"] for c in tables.get("userSvtCollection", [])}
    grand = {g["svtId"] for g in tables.get("userSvtGrand", [])}
    appends = {a["userSvtId"]: dict(zip(a["appendPassiveSkillNums"], a["appendPassiveSkillLvs"]))
               for a in tables.get("userSvtAppendPassiveSkillLv", [])}
    today = time.strftime("%Y-%m-%d")

    # Several copies of a servant can sit in the box (a fodder copy at Lv1): keep the best one.
    best: dict[int, dict] = {}
    for u in units:
        if u["svtId"] in servants:
            key = (u["lv"], u["treasureDeviceLv1"], u["skillLv1"] + u["skillLv2"] + u["skillLv3"])
            old = best.get(u["svtId"])
            if old is None or key > (old["lv"], old["treasureDeviceLv1"], old["skillLv1"] + old["skillLv2"] + old["skillLv3"]):
                best[u["svtId"]] = u

    old_roster = memory._load()
    roster = {}
    for svt_id, u in best.items():
        s = servants[svt_id]
        no = str(s["collectionNo"])
        entry = {
            "name": s["name"], "class": s["className"], "rarity": s["rarity"],
            "level": u["lv"], "np": u["treasureDeviceLv1"],
            "skills": [u["skillLv1"], u["skillLv2"], u["skillLv3"]],
            "ascension": u["limitCount"], "grails": u["exceedCount"], "fou": u["adjustAtk"] * 10,
            "bond": bond.get(svt_id), "grand": svt_id in grand,
        }
        if u["id"] in appends:
            entry["appends"] = [appends[u["id"]].get(n, 0) for n in range(100, 105)]
        kept = {k: v for k, v in old_roster.get(no, {}).items() if k in ("note", "np_version")}
        roster[no] = {**entry, **kept, "updated": today}
    memory._save(roster)

    copies: dict[int, list[dict]] = {}
    for u in units:
        if u["svtId"] in equips:
            copies.setdefault(u["svtId"], []).append(u)
    old_ces = json.loads(memory.CES.read_text()) if memory.CES.exists() else {}
    ces = {}
    for svt_id, group in copies.items():
        c = equips[svt_id]
        top = max(group, key=lambda u: (u["limitCount"], u["lv"]))
        no = str(c["collectionNo"])
        kept = {k: v for k, v in old_ces.get(no, {}).items() if k == "note"}
        ces[no] = {"name": c["name"], "rarity": c["rarity"], "level": top["lv"], "mlb": top["limitCount"] == 4,
                   "count": len(group), **kept, "updated": today}
    memory.CES.write_text(json.dumps(ces, ensure_ascii=False, indent=2) + "\n")

    with_appends = sum("appends" in e for e in roster.values())
    return (f"imported {path.name}: {len(roster)} servants ({sum(e['grand'] for e in roster.values())} Grand, "
            f"{with_appends} with appends), {len(ces)} craft essences")
