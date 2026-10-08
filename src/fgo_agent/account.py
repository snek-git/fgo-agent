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
    files = sorted(CAPTURES.glob("login-top-*.json"))
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


STRENGTHENING_WAR = 1001  # Atlas war 強化クエスト
SELECTED = 16  # userSvt status flag for servants marked 選択 in the game


def _quest_wars() -> dict[int, tuple[str, dict]]:
    """Interludes and strengthening quests by id, with their kind. Interludes are quest type
    "friendship" wherever Atlas files them: the older ones sit in the main story's
    singularities (Enkidu's first is in the 7th), not in war 1003 幕間の物語."""
    wars = atlas._cached("nice_war_lang_en.json", f"{atlas.API}/export/JP/nice_war_lang_en.json", atlas.EXPORT_MAX_AGE)
    quests = {}
    for w in wars:
        for spot in w["spots"]:
            for q in spot["quests"]:
                if q.get("type") == "friendship":
                    quests[q["id"]] = ("interlude", q)
                elif w["id"] == STRENGTHENING_WAR:
                    quests[q["id"]] = ("strengthening", q)
    return quests


def owned_servants(tables: dict) -> dict[int, dict]:
    """The best copy of each owned servant, by svtId."""
    servants = {s["id"] for s in atlas.servants()}
    owned: dict[int, dict] = {}
    for u in tables["userSvt"] + tables.get("userSvtStorage", []):
        if u["svtId"] in servants and u["limitCount"] >= owned.get(u["svtId"], {}).get("limitCount", -1):
            owned[u["svtId"]] = u
    return owned


def favorites(tables: dict) -> set[int]:
    """svtIds the user marked 選択 in the game's servant list."""
    return {u["svtId"] for u in tables["userSvt"] + tables.get("userSvtStorage", []) if u["status"] & SELECTED}


def cleared_quests(tables: dict) -> set[int]:
    return {q["questId"] for q in tables.get("userQuest", []) if q["clearNum"] > 0}


def quest_rows(tables: dict, kind: str | None = None) -> list[dict]:
    """Every uncleared interlude and strengthening quest of the user's servants, with what
    still blocks it (empty `missing` means it is open now)."""
    servants = {s["id"]: s for s in atlas.servants()}
    owned = owned_servants(tables)
    bond = {c["svtId"]: c["friendshipRank"] for c in tables.get("userSvtCollection", [])}
    cleared = cleared_quests(tables)
    favorite = favorites(tables)
    quests = _quest_wars()

    def missing(cond: dict) -> str | None:
        kind_, target, value = cond["type"], cond["targetId"], cond["value"]
        if kind_ == "questClear":
            return None if target in cleared else f"clear quest {atlas.quest_name(target)}"
        if kind_ == "svtLimit":
            have = owned.get(target, {}).get("limitCount", -1)
            return None if have >= value else f"ascension {value} (has {have})"
        if kind_ == "svtFriendship":
            have = bond.get(target, 0)
            return None if have >= value else f"bond {value} (has {have})"
        if kind_ in ("svtGet", "date"):
            return None
        return f"{kind_} {target} {value}"

    rows = []
    for svt_id in sorted(owned, key=lambda i: servants[i]["collectionNo"]):
        s = servants[svt_id]
        for qid in s.get("relateQuestIds", []):
            if qid in cleared or qid not in quests:
                continue
            quest_kind, q = quests[qid]
            if kind and quest_kind != kind:
                continue
            rows.append({
                "kind": quest_kind, "quest_id": qid, "name": q["name"], "ap": q.get("consume"),
                "phases": len(q["phases"]), "servant": s["collectionNo"], "servant_name": s["name"],
                "favorite": svt_id in favorite,
                "missing": sorted({m for c in q.get("releaseConditions", []) if (m := missing(c))}),
            })
    return sorted(rows, key=lambda r: not r["favorite"])  # stable: favourites first


def pending_quests(kind: str | None = None) -> str:
    """Interludes and strengthening quests of the user's servants that are not cleared yet,
    split into open ones and locked ones (with what is missing), from the last sync."""
    tables, when = _synced()
    rows = quest_rows(tables, kind)

    def line(r: dict) -> str:
        return (f"{'★ ' if r['favorite'] else ''}#{r['servant']} {r['servant_name']}: {r['kind']} "
                f"「{r['name']}」 (quest {r['quest_id']}, {r['ap'] or '?'} AP, {r['phases']} phases)")

    ordered = [line(r) for r in rows if not r["missing"]]
    locked_rows = [f"{line(r)} needs {', '.join(r['missing'])}" for r in rows if r["missing"]]
    return (f"from the account sync of {when}; quests cleared since then still show here\n"
            f"★ = the user's favourite (marked 選択 in game): do these first\n"
            f"OPEN ({len(ordered)}):\n" + ("\n".join(ordered) or "none")
            + f"\nLOCKED ({len(locked_rows)}):\n" + ("\n".join(locked_rows) or "none"))


def append_levels(tables: dict):
    """A function giving the five append skill levels of a userSvt unit. Levels are kept per
    copy (userSvtAppendPassiveSkillLv); an append unlocked with coins but never levelled only
    shows in the per-servant unlock table (userSvtAppendPassiveSkill), at level 1."""
    levels = {a["userSvtId"]: dict(zip(a["appendPassiveSkillNums"], a["appendPassiveSkillLvs"]))
              for a in tables.get("userSvtAppendPassiveSkillLv", [])}
    unlocked = {a["svtId"]: set(a["unlockNums"]) for a in tables.get("userSvtAppendPassiveSkill", [])}

    def of(unit: dict) -> list[int]:
        own, open_ = levels.get(unit["id"], {}), unlocked.get(unit["svtId"], set())
        return [own.get(n, 1 if n in open_ else 0) for n in range(100, 105)]

    return of


def import_capture(path: Path) -> str:
    tables = _tables(path)
    units = tables["userSvt"] + tables.get("userSvtStorage", [])
    servants = {s["id"]: s for s in atlas.servants()}
    equips = {c["id"]: c for c in atlas.craft_essences()}
    bond = {c["svtId"]: c["friendshipRank"] for c in tables.get("userSvtCollection", [])}
    grand = {g["svtId"] for g in tables.get("userSvtGrand", [])}
    appends_of = append_levels(tables)
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
        entry["appends"] = appends_of(u)
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

    with_appends = sum(any(e["appends"]) for e in roster.values())
    return (f"imported {path.name}: {len(roster)} servants ({sum(e['grand'] for e in roster.values())} Grand, "
            f"{with_appends} with appends), {len(ces)} craft essences")
