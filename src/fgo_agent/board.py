"""What the user still has to do, as data for the board (web page and desktop app).

Everything comes from the latest account capture (current state), Atlas (quests, materials,
art) and Chaldea's plan (targets the user set there). Nothing here is account-specific code:
the repo is public, so all account data is read from data/ and Chaldea's folder at runtime.
"""

import json
import time
from pathlib import Path

from . import account, atlas, memory

CHALDEA = Path.home() / ".local/opt/chaldea/userdata/user/userdata.json"
FARMS = memory.DATA / "farms"
APPLES = {"Golden Fruit": "gold", "Silver Fruit": "silver", "Bronze Fruit": "bronze", "Bronzed Cobalt Fruit": "copper"}


def face(s: dict, ascension: int = 4) -> str | None:
    faces = s.get("extraAssets", {}).get("faces", {}).get("ascension", {})
    return faces.get(str(max(1, min(ascension, 4)))) or next(iter(faces.values()), None)


def class_icon(s: dict) -> str:
    frame = 3 if s["rarity"] >= 4 else 2 if s["rarity"] == 3 else 1
    return f"https://static.atlasacademy.io/JP/ClassIcons/class{frame}_{s['classId']}.png"


def _servant_card(s: dict, favorite: bool, ascension: int = 4) -> dict:
    return {"no": s["collectionNo"], "name": s["name"], "class": s["className"], "rarity": s["rarity"],
            "face": face(s, ascension + 1), "class_icon": class_icon(s), "favorite": favorite}


def _plan_targets() -> dict[int, dict]:
    """Targets from the plan currently selected in Chaldea, by collection number."""
    if not CHALDEA.exists():
        return {}
    data = json.loads(CHALDEA.read_text())
    user = data["users"][data["curUserKey"]]
    plan = user["plans"][user["curSvtPlanNo"]]
    return {int(no): t for no, t in plan["servants"].items()}


def _steps(materials: dict, start: int, end: int) -> list[dict]:
    """Material entries for levels start..end-1 (Atlas keys a step by its starting level)."""
    return [materials[str(lv)] for lv in range(start, end) if str(lv) in materials]


def upgrades(tables: dict) -> dict:
    servants = {s["id"]: s for s in atlas.servants()}
    owned = account.owned_servants(tables)
    favorite = account.favorites(tables)
    targets = _plan_targets()
    items = {i["itemId"]: i["num"] for i in tables.get("userItem", [])}
    coins = {c["svtId"]: c["num"] for c in tables.get("userSvtCoin", [])}
    appends = {a["userSvtId"]: dict(zip(a["appendPassiveSkillNums"], a["appendPassiveSkillLvs"]))
               for a in tables.get("userSvtAppendPassiveSkillLv", [])}
    qp_have = tables["userGame"][0]["qp"]

    def have(item: dict) -> int:
        return coins.get(item["value"], 0) if item["type"] == "svtCoin" else items.get(item["id"], 0)

    rows, totals, qp_total = [], {}, 0
    for svt_id, u in owned.items():
        s = servants[svt_id]
        t = targets.get(s["collectionNo"])
        if not t:
            continue
        cur_app = [appends.get(u["id"], {}).get(n, 0) for n in range(100, 105)]
        cur = {"ascension": u["limitCount"], "skills": [u["skillLv1"], u["skillLv2"], u["skillLv3"]],
               "appends": cur_app, "grails": u["exceedCount"]}
        goal = {"ascension": max(cur["ascension"], t["ascension"]),
                "skills": [max(c, g) for c, g in zip(cur["skills"], t["skills"])],
                "appends": [max(c, g) for c, g in zip(cur_app, t["appendSkills"])],
                "grails": max(cur["grails"], t.get("grail", 0))}
        if goal == cur:
            continue
        steps = _steps(s["ascensionMaterials"], cur["ascension"], goal["ascension"])
        for c, g in zip(cur["skills"], goal["skills"]):
            steps += _steps(s["skillMaterials"], c, g)
        for num, (c, g) in enumerate(zip(cur_app, goal["appends"]), start=100):
            steps += _steps(s.get("appendSkillMaterials", {}), max(c, 1), g)
            if c == 0 and g > 0:  # unlocking the append costs servant coins
                unlock = next((p for p in s.get("appendPassive", []) if p["num"] == num), None)
                if unlock:
                    steps.append({"items": unlock.get("unlockMaterials", []), "qp": 0})
        need: dict[int, dict] = {}
        qp = 0
        for step in steps:
            qp += step.get("qp", 0)
            for entry in step["items"]:
                item = entry["item"]
                name = item["name"]
                if item["type"] == "svtCoin" and item["value"] in servants:  # every coin is called "Servant Coin"
                    name = f"{servants[item['value']]['name']} coin"
                row = need.setdefault(item["id"], {"id": item["id"], "name": name, "icon": item["icon"],
                                                   "need": 0, "have": have(item)})
                row["need"] += entry["amount"]
        for row in need.values():
            total = totals.setdefault(row["id"], {**row, "need": 0})
            total["need"] += row["need"]
        qp_total += qp
        rows.append({
            **_servant_card(s, svt_id in favorite, cur["ascension"]),
            "current": cur, "target": goal, "qp": qp,
            "materials": sorted(need.values(), key=lambda r: r["have"] - r["need"]),
            "can_do": all(r["have"] >= r["need"] for r in need.values()) and qp <= qp_have,
        })
    rows.sort(key=lambda r: (not r["favorite"], not r["can_do"], -r["rarity"], r["no"]))
    missing = sorted((r | {"missing": r["need"] - r["have"]} for r in totals.values() if r["need"] > r["have"]),
                     key=lambda r: -r["missing"])
    return {"servants": rows, "missing": missing, "qp": {"need": qp_total, "have": qp_have},
            "has_plan": bool(targets)}


def quests(tables: dict) -> dict:
    servants = {s["collectionNo"]: s for s in atlas.servants()}
    owned = account.owned_servants(tables)
    rows = []
    for r in account.quest_rows(tables):
        s = servants[r["servant"]]
        asc = owned.get(s["id"], {}).get("limitCount", 4)
        rows.append({**r, "servant": _servant_card(s, r["favorite"], asc)})
    return {"open": [r for r in rows if not r["missing"]], "locked": [r for r in rows if r["missing"]]}


def story(tables: dict) -> list[dict]:
    """Main story and free quests never cleared (free quests pay Saint Quartz on first clear)."""
    wars = atlas._cached("nice_war_lang_en.json", f"{atlas.API}/export/JP/nice_war_lang_en.json", atlas.EXPORT_MAX_AGE)
    cleared = account.cleared_quests(tables)
    now = time.time()
    groups = []
    for w in wars:
        if w.get("eventId", 0) or w["id"] >= 1000:
            continue
        todo = [{"quest_id": q["id"], "name": q["name"], "type": q["type"], "ap": q.get("consume"), "spot": spot["name"]}
                for spot in w["spots"] for q in spot["quests"]
                if q.get("type") in ("main", "free") and q["id"] not in cleared
                and q.get("consume", 0) < 999 and q.get("closedAt", 2e9) > now]
        if todo:
            groups.append({"war": w["id"], "name": w["longName"].replace("\n", " "), "banner": w.get("banner"),
                           "main": [q for q in todo if q["type"] == "main"],
                           "free": [q for q in todo if q["type"] == "free"]})
    return groups


def resources(tables: dict) -> dict:
    game = tables["userGame"][0]
    owned = {i["itemId"]: i["num"] for i in tables.get("userItem", [])}
    by_name = {item["name"]: item for item in atlas.items()}
    apples = {key: owned.get(by_name[name]["id"], 0) for name, key in APPLES.items() if name in by_name}
    icons = {key: by_name[name]["icon"] for name, key in APPLES.items() if name in by_name}
    icons |= {key: by_name[name]["icon"] for name, key in (("Saint Quartz", "saint_quartz"), ("QP", "qp"),
                                                            ("Mana Prism", "mana_prisms")) if name in by_name}
    return {"level": game["lv"], "ap_max": game["actMax"], "cost_max": game["costMax"], "qp": game["qp"],
            "saint_quartz": game["stone"], "mana_prisms": game["mana"], "rare_prisms": game["rarePri"],
            "apples": apples, "icons": icons, "command_spells_back": game["commandSpellRecoverAt"]}


def farms() -> list[dict]:
    """Saved 3-turn farming plans (written by the agent's exploratory runs)."""
    return [json.loads(p.read_text()) for p in sorted(FARMS.glob("*.json"))] if FARMS.exists() else []


def board() -> dict:
    path = account.latest_capture()
    tables = account._tables(path)
    return {"synced_at": path.stat().st_mtime, "resources": resources(tables), "quests": quests(tables),
            "upgrades": upgrades(tables), "story": story(tables), "farms": farms()}
