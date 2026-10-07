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


def _tables(path: Path) -> dict:
    return json.loads(path.read_text())["cache"]["replaced"]


def _synced() -> tuple[dict, str]:
    """The latest capture's tables and when it was taken, for the tools that read it directly."""
    path = latest_capture()
    return _tables(path), time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))


def summary() -> str:
    tables, when = _synced()
    game = tables["userGame"][0]
    codes = {m["id"]: m["name"] for m in atlas.mystic_codes()}
    mcs = ", ".join(f"{codes.get(e['equipId'], e['equipId'])} Lv{e['lv']}"
                    for e in sorted(tables.get("userEquip", []), key=lambda e: -e["lv"]))
    spells_back = time.strftime("%Y-%m-%d %H:%M", time.localtime(game["commandSpellRecoverAt"]))
    return (f"account data from {when} (it changes as you play; the user re-syncs it)\n"
            f"master Lv{game['lv']}, AP max {game['actMax']}, party cost cap {game['costMax']}\n"
            f"QP {game['qp']:,}, Saint Quartz {game['stone']} (never spend), mana prisms {game['mana']:,}, "
            f"rare prisms {game['rarePri']}\n"
            f"command spells: next one recovers {spells_back} (local time)\n"
            f"mystic codes: {mcs}\n"
            f"command codes owned: {len(tables.get('userCommandCode', []))}")


def inventory(query: str | None = None) -> str:
    tables, when = _synced()
    owned = {i["itemId"]: i["num"] for i in tables.get("userItem", [])}
    rows = []
    for item in atlas.items():
        num = owned.get(item["id"], 0)
        if num <= 0:
            continue
        if query:
            q = query.casefold()
            if q not in item["name"].casefold() and q not in item.get("originalName", "").casefold():
                continue
        elif not item.get("uses") and item["type"] != "apRecover":
            continue
        rows.append(f"{item['name']} ({item.get('originalName', '')}): {num:,}")
    if not rows:
        return f"no owned items match {query!r} (data from {when})"
    head = f"items from {when}" + ("" if query else ", materials and apples only (pass a name for others)")
    return head + "\n" + "\n".join(rows)


def find_owned(effect: str, target: str | None = None, class_name: str | None = None) -> str:
    """Owned servants whose skills or NP have an effect matching `effect` (e.g. "NP Seal",
    "Drain enemy charge", "Remove effects", "Ignore Invincible", "Taunt")."""
    roster = memory._load()
    if not roster:
        return "roster is empty: the user has to run scripts/capture-account.sh"
    by_no = {str(s["collectionNo"]): s for s in atlas.servants()}
    want = effect.casefold()
    rows = []
    for no, entry in sorted(roster.items(), key=lambda kv: (-kv[1].get("level", 0), kv[1]["name"])):
        s = by_no.get(no)
        if s is None or (class_name and s["className"].casefold() != class_name.casefold()):
            continue
        hits = []
        sources = [(f"S{sk.get('num', '?')} {sk['name']}", atlas.describe_skill(sk)) for sk in s["skills"]]
        sources += [(f"NP {np['name']}", atlas.describe_np(np)) for np in s["noblePhantasms"]]
        for where, text in sources:
            for line in text.splitlines():
                line = line.strip(" -")
                if want in line.casefold() and (not target or target.casefold() in line.casefold()):
                    hit = f"{where}: {line}"
                    if hit not in hits:
                        hits.append(hit)
        if hits:
            rows.append(f"#{no} {entry['name']} [{entry['class']}] {memory.format_entry({k: v for k, v in entry.items() if k != 'note'})}\n  "
                        + "\n  ".join(hits))
    if not rows:
        return f"none of the user's servants has an effect matching {effect!r}"
    return (f"{len(rows)} owned servants (skills list every version; check which one the user has):\n"
            + "\n".join(rows))


def import_capture(path: Path) -> str:
    tables = _tables(path)
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
