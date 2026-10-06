"""Atlas Academy game data (JP region, English names), turned into short text for the agent.

Bulk servant data comes from the daily export and is cached on disk. Quests, enemy skills and
the class tables come from the API and are cached per id.
"""

import difflib
import json
import time
import urllib.parse
import urllib.request
from functools import cache
from pathlib import Path

API = "https://api.atlasacademy.io"
CACHE = Path.home() / ".cache" / "fgo-agent"
EXPORT_MAX_AGE = 3 * 24 * 3600  # JP gets new servants and upgrades often

CARD = {"1": "A", "2": "B", "3": "Q", "4": "EX", "arts": "A", "buster": "B", "quick": "Q"}
TARGET = {
    "self": "self",
    "ptOne": "one ally (needs target)",
    "ptAll": "all allies",
    "ptFull": "all allies incl. backline",
    "ptOther": "other allies",
    "ptOneOther": "one other ally",
    "ptOtherFull": "other allies incl. backline",
    "enemy": "target enemy",
    "enemyAll": "all enemies",
    "enemyFull": "all enemies incl. reserves",
    "enemyOther": "other enemies",
    "ptRandom": "random ally",
    "enemyRandom": "random enemy",
    "ptselectOneSub": "one ally (swap)",
    "ptselectSub": "backline ally (swap)",
}
# Buff types whose Value is a flat number, not per mille.
FLAT_BUFFS = {"regainHp", "addMaxhp", "subMaxhp", "subSelfdamage", "addDamage", "subDamage",
              "regainStar", "guts", "upChagetd"}
NOISE_TRAITS = {"canBeInBattle", "notBasedOnServant", "basedOnServant", "unknown"}


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "fgo-agent"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _cached(name: str, url: str, max_age: float | None = None) -> object:
    path = CACHE / name
    fresh = path.exists() and (max_age is None or time.time() - path.stat().st_mtime < max_age)
    if not fresh:
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(_get(url))
        tmp.replace(path)
    return json.loads(path.read_text())


@cache
def servants() -> list[dict]:
    return _cached("nice_servant_lang_en.json", f"{API}/export/JP/nice_servant_lang_en.json", EXPORT_MAX_AGE)


@cache
def class_relation() -> dict:
    return _cached("NiceClassRelation.json", f"{API}/export/JP/NiceClassRelation.json", EXPORT_MAX_AGE)


@cache
def attribute_relation() -> dict:
    return _cached("NiceAttributeRelation.json", f"{API}/export/JP/NiceAttributeRelation.json", EXPORT_MAX_AGE)


def quest_phase(quest_id: int, phase: int) -> dict:
    return _cached(f"quest_{quest_id}_{phase}.json", f"{API}/nice/JP/quest/{quest_id}/{phase}?lang=en")


def skill(skill_id: int) -> dict:
    return _cached(f"skill_{skill_id}.json", f"{API}/nice/JP/skill/{skill_id}?lang=en")


def noble_phantasm(np_id: int) -> dict:
    return _cached(f"np_{np_id}.json", f"{API}/nice/JP/NP/{np_id}?lang=en")


def search_quests(name: str) -> list[dict]:
    """Search by the quest's Japanese name as shown in game (partial match works)."""
    url = f"{API}/basic/JP/quest/phase/search?lang=en&name={urllib.parse.quote(name)}"
    return json.loads(_get(url))


# --- finding servants ---

def find_servants(query: str, limit: int = 5) -> list[dict]:
    """Match by collection number, English name, Japanese name, or fuzzy English name."""
    q = query.strip()
    pool = [s for s in servants() if s["collectionNo"] > 0]
    if q.isdigit():
        return [s for s in pool if s["collectionNo"] == int(q)][:limit]
    folded = q.casefold()
    exact = [s for s in pool if folded in (s["name"].casefold(), s["originalName"], s["battleName"].casefold())]
    if exact:
        return exact[:limit]
    partial = [s for s in pool if folded in s["name"].casefold() or q in s["originalName"]
               or folded in s["battleName"].casefold() or q in s["originalBattleName"]]
    if partial:
        return partial[:limit]
    names = {s["name"]: s for s in pool}
    return [names[n] for n in difflib.get_close_matches(q, list(names), n=limit, cutoff=0.5)]


# --- describing effects ---

def _num(value: float) -> str:
    return f"{value:g}"


def _value(func: dict, vals: dict) -> str:
    v = vals.get("Value")
    kind = func["funcType"]
    if v is None:
        return ""
    if kind.startswith("damageNp"):
        return f"{_num(v / 10)}%"
    if kind in ("gainNp", "lossNp", "gainNpFromTargets", "gainNpBuffIndividualSum"):
        return f"{_num(v / 100)}%"
    if kind in ("gainStar", "lossStar"):
        return f"{v} stars"
    if kind in ("gainHp", "lossHp", "lossHpSafe"):
        return f"{v} HP"
    if kind == "gainHpPer":
        return f"{_num(v / 10)}% HP"
    if kind in ("shortenSkill", "extendSkill", "delayNpturn", "lossNpturn", "hastenNpturn"):
        return f"{v}"
    buff = func["buffs"][0] if func["buffs"] else None
    if buff is None:
        return str(v)
    if buff["type"] == "regainNp":
        return f"{_num(v / 100)}% NP/turn"
    if buff["type"] in FLAT_BUFFS:
        return str(v)
    return f"{_num(v / 10)}%"


def _label(func: dict) -> str:
    kind = func["funcType"]
    if func["buffs"]:
        buff = func["buffs"][0]
        label = buff["name"]
        against = [t["name"] for t in buff.get("ckOpIndv", []) if t["name"] not in NOISE_TRAITS]
        if against:
            label += f" vs {'/'.join(against)}"
        return label
    names = {
        "gainNp": "Charge NP", "lossNp": "Drain NP", "gainStar": "Gain stars", "gainHp": "Heal",
        "gainHpPer": "Heal", "subState": "Remove effects", "instantDeath": "Instant death",
        "shortenSkill": "Reduce skill cooldowns by", "delayNpturn": "Drain enemy charge by",
        "hastenNpturn": "Raise charge by", "gainNpFromTargets": "Absorb NP",
        "cardReset": "Shuffle cards", "transformServant": "Transform", "replaceMember": "Order change",
    }
    if kind.startswith("damageNp"):
        return "NP damage"
    return names.get(kind, kind)


def _series(func: dict, key: str) -> list[dict]:
    return func.get(key) or []


def _describe_func(func: dict, levels: list[dict], note_oc: list[dict] | None = None) -> str:
    """One effect line. `levels` holds the svals per skill/NP level; `note_oc` the OC500 svals."""
    first, last = levels[0], levels[-1]
    a, b = _value(func, first), _value(func, last)
    value = a if a == b else f"{a}~{b}"
    if note_oc and _value(func, note_oc[0]) != a:
        value += f" (OC500: {_value(func, note_oc[0])})"
    target = TARGET.get(func["funcTargetType"], func["funcTargetType"])
    bits = [f"{_label(func)} {value}".strip(), f"-> {target}"]
    if first.get("Turn", -1) > 0:
        bits.append(f"{first['Turn']}T")
    if first.get("Count", -1) > 0:
        bits.append(f"{first['Count']} times")
    rate = first.get("Rate", 1000)
    if 0 < rate < 1000:
        bits.append(f"{_num(rate / 10)}% chance")
    if func["funcType"].startswith("damageNp") and "Correction" in first:
        bits.append(f"special x{_num(first['Correction'] / 1000)}")
    return " ".join(bits)


def describe_skill(sk: dict) -> str:
    cd = sk.get("coolDown") or [0]
    lines = [f"{sk['name']} ({sk['originalName']}) CD {cd[0]}~{cd[-1]}" if len(cd) > 1 else sk["name"]]
    for func in sk["functions"]:
        if func["svals"]:
            lines.append("  - " + _describe_func(func, func["svals"]))
    return "\n".join(lines)


def describe_np(np: dict) -> str:
    cards = CARD.get(str(np["card"]), str(np["card"]))
    hits = len(np.get("npDistribution") or [])
    lines = [f"NP {np['name']} ({np['originalName']}) [{cards}, {hits} hits]"]
    for func in np["functions"]:
        if func["svals"]:
            lines.append("  - " + _describe_func(func, func["svals"], _series(func, "svals5")))
    return "\n".join(lines)


def _latest(items: list[dict], key: str) -> list[dict]:
    """Newest upgrade per slot (FGO keeps every strengthened version)."""
    best: dict = {}
    for item in items:
        slot = item.get(key, 0)
        if slot not in best or (item.get("priority", 0), item["id"]) > (best[slot].get("priority", 0), best[slot]["id"]):
            best[slot] = item
    return [best[k] for k in sorted(best)]


def describe_servant(s: dict) -> str:
    deck = "".join(CARD.get(c, c) for c in s["cards"])
    np_gain = s["noblePhantasms"][-1].get("npGain", {}) if s["noblePhantasms"] else {}
    gain = ", ".join(f"{CARD[k]} {_num(v[0] / 100)}%" for k, v in np_gain.items() if k in ("arts", "buster", "quick") and v)
    traits = [t["name"] for t in s["traits"] if t["name"] not in NOISE_TRAITS and not t["name"].startswith(("class", "attribute"))]
    lines = [
        f"#{s['collectionNo']} {s['name']} ({s['originalName']}), {s['rarity']}* {s['className']}, {s['attribute']}",
        f"Deck {deck} | ATK {s['atkMax']} HP {s['hpMax']} | NP gain/hit: {gain} | star gen {_num(s['starGen'] / 10)}%",
        f"Traits: {', '.join(traits[:14])}",
        "Skills:",
    ]
    lines += ["  " + describe_skill(sk).replace("\n", "\n  ") for sk in _latest(s["skills"], "num")]
    lines.append("Passives: " + "; ".join(p["name"] for p in s["classPassive"]))
    nps = [np for np in s["noblePhantasms"] if np["functions"]]
    if nps:
        lines.append(describe_np(_latest(nps, "num")[-1]))
    return "\n".join(lines)


# --- battle brief ---

def _multiplier(table: dict, attacker: str, defender: str) -> float:
    return table.get(attacker, {}).get(defender, 1000) / 1000


def describe_enemy(enemy: dict, party: list[dict]) -> str:
    svt = enemy["svt"]
    traits = [t["name"] for t in enemy["traits"] if t["name"] not in NOISE_TRAITS
              and not t["name"].startswith(("class", "attribute"))]
    head = (f"{enemy['name']} ({svt['originalName']}) {svt['className']}/{svt['attribute']} "
            f"HP {enemy['hp']:,} charge {enemy.get('chargeTurn', 0)}")
    lines = [head, f"    traits: {', '.join(traits[:10])}"]
    extras = []
    for n in (1, 2, 3):
        skill_id = enemy["skills"].get(f"skillId{n}")
        if skill_id:
            extras.append(skill(skill_id)["name"])
    np_id = enemy["noblePhantasm"].get("noblePhantasmId")
    if np_id:
        np = noble_phantasm(np_id)
        extras.append(f"NP {np['name']} ({CARD.get(str(np['card']), np['card'])})")
    if extras:
        lines.append(f"    skills: {', '.join(extras)}")
    if party:
        cls, att = class_relation(), attribute_relation()
        vs = []
        for s in party:
            deal = _multiplier(cls, s["className"], svt["className"]) * _multiplier(att, s["attribute"], svt["attribute"])
            take = _multiplier(cls, svt["className"], s["className"]) * _multiplier(att, svt["attribute"], s["attribute"])
            vs.append(f"{s['name']} deals x{_num(round(deal, 2))} takes x{_num(round(take, 2))}")
        lines.append("    vs party: " + "; ".join(vs))
    return "\n".join(lines)


def battle_brief(quest_id: int, phase: int, party: list[dict]) -> str:
    q = quest_phase(quest_id, phase)
    name = q["name"].replace("\n", " ")
    lines = [f"Quest {name} ({q['originalName']}) id {quest_id} phase {phase}, "
             f"{q['warLongName']}, AP {q['consume']}, rec. lv {q['recommendLv']}"]
    for stage in q["stages"]:
        lines.append(f"Wave {stage['wave']}:")
        if not stage["enemies"]:
            lines.append("  (Atlas has no enemy data for this wave, read it off the screen)")
        for enemy in sorted(stage["enemies"], key=lambda e: e["deckId"]):
            if enemy.get("deck", "enemy") == "enemy":
                lines.append("  " + describe_enemy(enemy, party))
            else:
                lines.append(f"  (reserve) {enemy['name']} {enemy['svt']['className']} HP {enemy['hp']:,}")
    if party:
        lines.append("Party:")
        for s in party:
            lines.append(describe_servant(s))
    return "\n".join(lines)
