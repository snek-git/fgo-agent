"""Atlas Academy game data (JP region, English names), turned into short text for the agent.

Bulk servant data comes from the daily export and is cached on disk. Quests, enemy skills and
the class tables come from the API and are cached per id.
"""

import difflib
import json
import re
import time
import unicodedata
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
def craft_essences() -> list[dict]:
    return _cached("nice_equip_lang_en.json", f"{API}/export/JP/nice_equip_lang_en.json", EXPORT_MAX_AGE)


@cache
def mystic_codes() -> list[dict]:
    return _cached("nice_mystic_code_lang_en.json", f"{API}/export/JP/nice_mystic_code_lang_en.json", EXPORT_MAX_AGE)


@cache
def command_codes() -> list[dict]:
    return _cached("nice_command_code_lang_en.json", f"{API}/export/JP/nice_command_code_lang_en.json", EXPORT_MAX_AGE)


@cache
def class_relation() -> dict:
    return _cached("NiceClassRelation.json", f"{API}/export/JP/NiceClassRelation.json", EXPORT_MAX_AGE)


@cache
def attribute_relation() -> dict:
    return _cached("NiceAttributeRelation.json", f"{API}/export/JP/NiceAttributeRelation.json", EXPORT_MAX_AGE)


@cache
def class_attack_rate() -> dict:
    return _cached("NiceClassAttackRate.json", f"{API}/export/JP/NiceClassAttackRate.json", EXPORT_MAX_AGE)


# --- damage ---

CARD_DAMAGE = {"B": 1.5, "A": 1.0, "Q": 0.8}


def np_damage(s: dict, np_level: int, level: int, overcharge: int, enemy_class: str, enemy_attribute: str,
              atk_up: float = 0, card_up: float = 0, np_up: float = 0, def_down: float = 0,
              power_up: float = 0, special: bool = False, extra_atk: int = 1000, atk_down: float = 0,
              np_name: str | None = None, ratio: float = 1.0) -> dict:
    """Standard FGO NP damage formula. Buff arguments are percentages (30 = +30%).

    0.23 * ATK * NP% * card * (1 + card up) * class ATK rate * class triangle * attribute
         * (1 + ATK up - ATK down + DEF down) * (1 + NP damage up + power mod) * special,
         times 0.9 to 1.099, times the calibration ratio.
    Buff caps applied: card up 400%, ATK mod -100% to 400%, NP damage up 500%.
    np_name picks the NP version the player owns; without it the newest version is used.
    """
    nps = [np for np in s["noblePhantasms"]
           if any(f["funcType"].startswith("damageNp") for f in np["functions"])]
    if not nps:
        raise ValueError(f"{s['name']} has no damaging NP")
    if np_name:
        named = [np for np in nps if np_name.casefold() in np["name"].casefold()]
        if not named:
            names = sorted({np["name"] for np in nps})
            raise ValueError(f"{s['name']} has no damaging NP named {np_name!r}; versions: {', '.join(names)}")
        nps = named
    np = _versions(nps, "num")[max(_versions(nps, "num"))][-1]  # newest version of the last NP slot
    func = next(f for f in np["functions"] if f["funcType"].startswith("damageNp"))
    oc = min(max(overcharge, 1), 5)
    svals = func.get(f"svals{oc}") if oc > 1 else func["svals"]
    sval = (svals or func["svals"])[min(max(np_level, 1), len(func["svals"])) - 1]

    card = CARD.get(str(np["card"]), "B")
    atk = s["atkGrowth"][min(level, len(s["atkGrowth"])) - 1] + extra_atk
    rate = class_attack_rate().get(s["className"], 1000) / 1000
    triangle = _multiplier(class_relation(), s["className"], enemy_class)
    attribute = _multiplier(attribute_relation(), s["attribute"], enemy_attribute)
    card_mod = 1 + min(card_up, 400) / 100
    atk_mod = 1 + min(max(atk_up - atk_down + def_down, -100), 400) / 100
    np_mod = 1 + min(np_up + power_up, 500) / 100
    special_mod = sval.get("Correction", 1000) / 1000 if special and "Correction" in sval else 1.0

    base = (0.23 * atk * sval["Value"] / 1000 * CARD_DAMAGE[card] * card_mod * rate * triangle * attribute
            * atk_mod * np_mod * special_mod * ratio)
    return {
        "np": np["name"], "card": card, "hits": len(np.get("npDistribution") or []), "atk": atk,
        "np_percent": sval["Value"] / 10, "class_rate": rate, "triangle": triangle, "attribute": attribute,
        "special": special_mod, "min": round(base * 0.9), "avg": round(base), "max": round(base * 1.099),
        "has_special": "Correction" in sval,
    }


def quest_phase(quest_id: int, phase: int) -> dict:
    return _cached(f"quest_{quest_id}_{phase}.json", f"{API}/nice/JP/quest/{quest_id}/{phase}?lang=en")


def skill(skill_id: int) -> dict:
    return _cached(f"skill_{skill_id}.json", f"{API}/nice/JP/skill/{skill_id}?lang=en")


def noble_phantasm(np_id: int) -> dict:
    return _cached(f"np_{np_id}.json", f"{API}/nice/JP/NP/{np_id}?lang=en")


def _norm(text: str) -> str:
    """Fold the variants the game and a reader mix up: Ⅰ/I, full-width/half-width, case, spaces."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).casefold()


@cache
def quest_index() -> list[dict]:
    """Every quest in every war. Atlas's phase search skips many event quests, this doesn't."""
    wars = _cached("nice_war_lang_en.json", f"{API}/export/JP/nice_war_lang_en.json", EXPORT_MAX_AGE)
    index = []
    for war in wars:
        war_name = war.get("originalLongName") or war.get("originalName") or ""
        for spot in war["spots"]:
            for q in spot["quests"]:
                names = [q["name"], q.get("originalName", ""), f"{war_name} {q.get('originalName', '')}"]
                index.append({
                    "id": q["id"], "name": q["name"].replace("\n", " "), "originalName": q.get("originalName", ""),
                    "war": war.get("longName", "").replace("\n", " "), "spot": q.get("spotName", ""),
                    "consume": q.get("consume"), "phases": q.get("phases", []),
                    "phasesWithEnemies": q.get("phasesWithEnemies", []),
                    "keys": [_norm(n) for n in names if n],
                })
    return index


def search_quests(name: str, limit: int = 25) -> list[dict]:
    """Find quests by the name shown in game. Partial names and Ⅰ/I-style variants match;
    falls back to fuzzy matching when nothing contains the query."""
    query = _norm(name)
    hits = [q for q in quest_index() if any(query in key for key in q["keys"])]
    if not hits:
        scored = [(max(difflib.SequenceMatcher(None, query, key).ratio() for key in q["keys"]), q)
                  for q in quest_index()]
        hits = [{**q, "fuzzy": True} for score, q in sorted(scored, key=lambda s: -s[0]) if score >= 0.6]
    return hits[:limit]


# --- finding things by name ---

def find(pool: list[dict], query: str, limit: int = 5) -> list[dict]:
    """Match by collection number (or id), English name, Japanese name, or fuzzy English name."""
    q = query.strip()
    if q.isdigit():
        n = int(q)
        return [x for x in pool if x.get("collectionNo", x["id"]) == n or x["id"] == n][:limit]
    folded = q.casefold()

    def names(x: dict) -> list[str]:
        return [x["name"], x["originalName"], x.get("battleName", ""), x.get("originalBattleName", ""),
                x.get("shortName", "")]

    exact = [x for x in pool if any(folded == n.casefold() for n in names(x) if n)]
    if exact:
        return exact[:limit]
    partial = [x for x in pool if any(folded in n.casefold() for n in names(x) if n)]
    if partial:
        return partial[:limit]
    by_name = {x["name"]: x for x in pool}
    return [by_name[n] for n in difflib.get_close_matches(q, list(by_name), n=limit, cutoff=0.5)]


def find_servants(query: str, limit: int = 5) -> list[dict]:
    return find([s for s in servants() if s["collectionNo"] > 0], query, limit)


def find_craft_essences(query: str, limit: int = 5) -> list[dict]:
    return find([c for c in craft_essences() if c["collectionNo"] > 0], query, limit)


def find_mystic_codes(query: str, limit: int = 5) -> list[dict]:
    return find(mystic_codes(), query, limit)


def find_command_codes(query: str, limit: int = 5) -> list[dict]:
    return find(command_codes(), query, limit)


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
        if against and " vs" not in label:
            label += f" vs {'/'.join(against)}"
        return label
    names = {
        "gainNp": "Charge NP", "lossNp": "Drain NP", "gainStar": "Gain stars", "gainHp": "Heal",
        "gainHpPer": "Heal", "subState": "Remove effects", "instantDeath": "Instant death",
        "shortenSkill": "Reduce skill cooldowns by", "delayNpturn": "Drain enemy charge by",
        "hastenNpturn": "Raise charge by", "gainNpFromTargets": "Absorb NP",
        "lossHp": "Lose HP", "lossHpSafe": "Lose HP (non-lethal)", "lossStar": "Lose stars",
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
    value = a
    if a != b:
        ma, mb = re.match(r"^([\d.]+)(.*)$", a), re.match(r"^([\d.]+)(.*)$", b)
        same_unit = ma and mb and ma.group(2) == mb.group(2)
        value = f"{ma.group(1)}~{mb.group(1)}{ma.group(2)}" if same_unit else f"{a}~{b}"
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


def _shown(func: dict) -> bool:
    """Skip hidden bookkeeping functions (no values, or no effect and no visible buff)."""
    if not func["svals"] or func["funcType"] == "none":
        return False
    return not func["buffs"] or bool(func["buffs"][0].get("name")) and func["buffs"][0]["type"] != "none"


def describe_skill(sk: dict) -> str:
    cd = sk.get("coolDown") or [0]
    lines = [f"{sk['name']} ({sk['originalName']}) CD {cd[0]}~{cd[-1]}" if len(cd) > 1 else sk["name"]]
    for func in sk["functions"]:
        if _shown(func):
            lines.append("  - " + _describe_func(func, func["svals"]))
    return "\n".join(lines)


def describe_np(np: dict) -> str:
    cards = CARD.get(str(np["card"]), str(np["card"]))
    hits = len(np.get("npDistribution") or [])
    lines = [f"NP {np['name']} ({np['originalName']}) [{cards}, {hits} hits]"]
    for func in np["functions"]:
        if _shown(func):
            lines.append("  - " + _describe_func(func, func["svals"], _series(func, "svals5")))
    return "\n".join(lines)


@cache
def quest_name(quest_id: int) -> str:
    q = _cached(f"quest_{quest_id}.json", f"{API}/nice/JP/quest/{quest_id}?lang=en")
    return q["name"].replace("\n", " ")


def _unlock(item: dict) -> str:
    parts = []
    if item.get("condQuestId"):
        parts.append(f"after quest '{quest_name(item['condQuestId'])}'")
    if item.get("condLimitCount"):
        parts.append(f"ascension {item['condLimitCount']}+")
    return ", ".join(parts) or "base"


def _versions(items: list[dict], key: str) -> dict[int, list[dict]]:
    """Every version per slot, base first. Which one a player has depends on their story
    progress, rank-up quests and ascension, so the agent gets all of them."""
    slots: dict[int, list[dict]] = {}
    for item in items:
        slots.setdefault(item.get(key, 0), []).append(item)
    order = lambda i: (bool(i.get("condQuestId")), i.get("condLimitCount", 0), i.get("priority", 0), i["id"])  # noqa: E731
    return {slot: sorted(group, key=order) for slot, group in sorted(slots.items())}


def _describe_versions(items: list[dict], key: str, describe) -> list[str]:
    lines = []
    for slot, group in _versions(items, key).items():
        seen: set[str] = set()
        texts = []
        for v in group:
            text = describe(v)
            if text not in seen:  # Atlas keeps identical copies under different ids
                seen.add(text)
                texts.append(f"[{_unlock(v)}] {text}")
        if len(texts) == 1:
            lines.append(texts[0].split("] ", 1)[1])
            continue
        lines.append(f"Slot {slot} has {len(texts)} versions, check the in-game name to know which applies:")
        lines += texts
    return lines


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
    own = [sk for sk in s["skills"]
           if not sk.get("skillSvts") or any(x["svtId"] == s["id"] for x in sk["skillSvts"])]
    lines += ["  " + text.replace("\n", "\n  ") for text in _describe_versions(own, "num", describe_skill)]
    lines.append("Passives: " + "; ".join(p["name"] for p in s["classPassive"]))
    nps = [np for np in s["noblePhantasms"] if np["functions"]]
    lines += _describe_versions(nps, "num", describe_np)
    return "\n".join(lines)


def _effects(sk: dict) -> list[str]:
    return ["  - " + _describe_func(f, f["svals"]) for f in sk["functions"] if _shown(f)]


def describe_craft_essence(ce: dict) -> str:
    lines = [f"CE #{ce['collectionNo']} {ce['name']} ({ce['originalName']}), {ce['rarity']}*, "
             f"ATK {ce['atkMax']} HP {ce['hpMax']}"]
    by_limit = sorted(ce["skills"], key=lambda s: (s.get("condLimitCount", 0), s.get("priority", 0)))
    for sk in by_limit:
        label = "MLB" if sk.get("condLimitCount", 0) >= 4 else "Base"
        lines.append(f"{label}:")
        lines += _effects(sk)
    return "\n".join(lines)


def describe_mystic_code(mc: dict) -> str:
    lines = [f"Mystic Code {mc['name']} ({mc['originalName']}), skills at lv1~lv{mc.get('maxLv', 10)}:"]
    lines += ["  " + describe_skill(sk).replace("\n", "\n  ") for sk in mc["skills"]]
    return "\n".join(lines)


def describe_command_code(cc: dict) -> str:
    lines = [f"Command Code #{cc['collectionNo']} {cc['name']} ({cc['originalName']}), {cc['rarity']}*"]
    for sk in cc["skills"]:
        lines += _effects(sk)
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
        if svt["className"] not in cls:
            lines.append(f"    vs party: unknown, class {svt['className']} is not in Atlas's class table "
                         "(special enemy class; check the in-game class icon and quest hints)")
        else:
            lines.append("    vs party: " + "; ".join(vs))
    return "\n".join(lines)


def battle_brief(quest_id: int, phase: int, party: list[dict], ces: list[dict | None] | None = None,
                 mystic_code: dict | None = None) -> str:
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
        for i, s in enumerate(party):
            lines.append(describe_servant(s))
            ce = ces[i] if ces and i < len(ces) else None
            if ce:
                lines.append("Equipped " + describe_craft_essence(ce))
    if mystic_code:
        lines.append(describe_mystic_code(mystic_code))
    return "\n".join(lines)
