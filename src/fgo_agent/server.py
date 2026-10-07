"""MCP server that lets an AI agent see and play FGO in the redroid container.

Battle mechanics (when the game is ready, casting, targeting, cards, the screens between turns)
run in FGA's own code through the bridge. The agent makes every decision.
"""

import json
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

from mcp.server.mcpserver import Image, MCPServer

from . import account, atlas, memory
from .bridge import Bridge
from .device import Device, encode_jpeg

INSTRUCTIONS = """\
You are playing Fate/Grand Order (JP) on an Android container. The screen is 1280x720 and
tap/swipe coordinates are those pixels, so read positions straight off the screenshot.
Start with `look`. After anything that starts animations or loading (a battle turn, starting a
quest, leaving results) call `advance`: it runs FGA's handling of story skip, results, drops,
bond and wave transitions, and returns when you have a decision to make.
In battle, act with FGA's skill notation (`act`), then `open_cards` and `play_cards`.
Before a quest, read its Japanese name off the screen, call `find_quest`, then `prepare_battle`
so you know every wave's enemies and your own kit.
Set your goal with `set_goal` at the start; it is echoed in every result. Before spending
skills on a bar, check `estimate_np_damage`: use only what the bar needs.
You keep memory between sessions: start every session with `read_notes`. `roster`, `list_ces`,
`inventory` and `account_summary` hold the user's account as synced from the game; when a
fight needs a mechanic (NP seal, charge drain, buff removal, taunt), `find_owned` lists which
of the user's servants have it. Record lessons, UI quirks and battle results in notes
(`write_note`), and NP versions or anything newer than the sync with `update_servant`.
Apples may be used to refill AP. Never spend Saint Quartz (聖晶石), summon, or buy anything
unless the user told you to. Command spells (令呪) are a last resort: plan to win without them.
A clear that needed command spells is not a success; say so in your report and battle note."""

PROJECT = Path(__file__).resolve().parents[2]
mcp = MCPServer("fgo", instructions=INSTRUCTIONS)
_device: Device | None = None
_bridge: Bridge | None = None
_brief: str | None = None


def device() -> Device:
    global _device
    if _device is None:
        _device = Device()
    return _device


def bridge() -> Bridge:
    global _bridge
    if _bridge is None:
        _bridge = Bridge()
    return _bridge


_last_thumb: np.ndarray | None = None
_unchanged = 0


def _view(state: dict | None = None, acted: bool = True) -> list:
    """Fresh screenshot plus state. After an action, warns when the screen stopped changing:
    long-running agents loop on taps that do nothing (other harnesses lost hours to this)."""
    global _last_thumb, _unchanged
    state = dict(state or {})
    if "screen" not in state:
        state["screen"] = bridge().call("screen")["screen"]
    if state["screen"] == "battle" and "battle" not in state:
        state["battle"] = bridge().call("battle")["battle"]
    if _brief and state["screen"] == "battle":
        state["brief"] = "battle brief loaded, call battle_brief to re-read it"
    if goal := memory.goal():
        state["goal"] = goal
    image = device().screenshot()
    thumb = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (64, 36), interpolation=cv2.INTER_AREA)
    if acted and _last_thumb is not None and float(cv2.absdiff(thumb, _last_thumb).mean()) < 1.5:
        _unchanged += 1
    elif acted:
        _unchanged = 0
    _last_thumb = thumb
    if _unchanged >= 3:
        state["warning"] = (f"the screen has not changed after your last {_unchanged} actions; stop repeating "
                            "them: read the screenshot again, then try a different element or back")
    return [json.dumps(state, ensure_ascii=False), Image(data=encode_jpeg(image), format="jpeg")]


@mcp.tool()
def look() -> list:
    """Screenshot plus FGA's reading of which screen is up (battle, menu, support, repeat,
    ap_refill, withdraw, ...; "unknown" when none of FGA's detectors match). In battle it
    adds the wave, the turn within that wave, and which party member (1-6) is in each field
    slot (1-3)."""
    return _view(acted=False)


@mcp.tool()
def set_goal(goal: str) -> str:
    """Set the current goal and next step in one or two lines, e.g. "Clear Grand Duel Extra I.
    Next: pick a Buster support". Every tool result echoes it back, so it survives long sessions;
    update it whenever the plan changes. It is also kept for the next session."""
    memory.set_goal(goal)
    return f"goal set: {goal}"


@mcp.tool()
def advance(timeout: int = 120) -> list:
    """Let FGA's loop run until there is a decision for you: it skips story, taps through
    result, bond, drops and reward screens, rejects friend requests, waits out NP and wave
    animations. Returns the screen it stopped on: battle (your turn), menu, support, repeat,
    ap_refill, withdraw, inventory_full, close_dialog (a dialog with a 閉じる button: read
    it), unknown (a screen none of FGA's detectors know: popups, tutorial pages, summon
    screens; read the screenshot and tap), or timeout."""
    return _view(bridge().call("advance", timeout=timeout))


@mcp.tool()
def tap(x: int, y: int, wait: float = 1.0) -> list:
    """Tap at screen pixel (x, y), wait `wait` seconds, then return a fresh look.
    For menus and anything outside battle."""
    device().tap(x, y)
    time.sleep(wait)
    return _view()


@mcp.tool()
def swipe(x1: int, y1: int, x2: int, y2: int, ms: int = 400, wait: float = 1.0) -> list:
    """Swipe between two screen pixels (scroll lists), then return a fresh look."""
    device().swipe(x1, y1, x2, y2, ms)
    time.sleep(wait)
    return _view()


@mcp.tool()
def back(wait: float = 1.0) -> list:
    """Press Android back, then return a fresh look."""
    device().back()
    time.sleep(wait)
    return _view()


@mcp.tool()
def wait(seconds: float = 3.0) -> list:
    """Do nothing for a while (max 60s), then return a fresh look."""
    time.sleep(min(seconds, 60))
    return _view()


@mcp.tool()
def launch_fgo() -> list:
    """Start the FGO app if it is not running."""
    if not device().fgo_running():
        device().launch_fgo()
        time.sleep(8)
    return _view()


@mcp.tool()
def act(command: str) -> list:
    """Battle, your turn: run actions with FGA's skill notation, through FGA's caster (it
    confirms, targets and waits for each animation). One turn only, no ',' or '#'.
    Servant skills by field slot: a b c (slot 1), d e f (slot 2), g h i (slot 3).
    Ally target right after the skill: 1 2 3 (by field slot), e.g. "b1" = slot 1 skill 2 on
    slot 1. Master skills: j k l. Enemy target: t1 t2 t3 are the fixed enemy positions in the
    top HP-bar row, left to right; a wave with fewer enemies leaves some empty. Order change:
    x then the starting member 1-3 and backline member 1-3, e.g. "x13". NP-charge command
    spell: o then target. Several actions chain: "ad3j"."""
    bridge().call("act", command=command)
    return _view()


@mcp.tool()
def open_cards() -> list:
    """Battle: press Attack and read the hand with FGA's card parser: type, weak/resist,
    stunned, and which party member owns each card (servant 1-6, 0 unknown)."""
    cards = bridge().call("cards")["cards"]
    return _view({"screen": "cards", "cards": cards})


@mcp.tool()
def play_cards(cards: list[int], nps: list[int] | None = None, cards_before_np: int = 0) -> list:
    """Battle, on the card screen: play noble phantasms `nps` (field slots 1-3) and face
    cards `cards` (1-5 left to right, in play order), three picks in total. NPs go first
    unless `cards_before_np` (0-2) says how many face cards come before them.
    Then runs `advance` until the next decision."""
    bridge().call("play", nps=nps or [], cards=cards, cards_before_np=cards_before_np)
    return _view(bridge().call("advance", timeout=120))


@mcp.tool()
def close_cards() -> list:
    """Battle: leave the card screen to use more skills."""
    bridge().call("back")
    return _view()


def _lookup(kind: str, matches: list[dict], describe, query: str) -> str:
    if not matches:
        return f"no {kind} matches {query!r}"
    text = describe(matches[0])
    if len(matches) > 1:
        others = ", ".join(f"#{m.get('collectionNo', m['id'])} {m['name']}" for m in matches[1:])
        text += f"\n\nOther matches: {others}"
    return text


@mcp.tool()
def lookup_servant(query: str) -> str:
    """Servant data from Atlas Academy (JP, English names): deck, NP gain, skills with
    level 1~10 values and cooldowns, passives, NP effects. Query by English name, Japanese
    name, or collection number."""
    return _lookup("servant", atlas.find_servants(query), atlas.describe_servant, query)


@mcp.tool()
def lookup_ce(query: str) -> str:
    """Craft Essence effects, base and max limit break (MLB), plus ATK/HP.
    Query by English name, Japanese name, or collection number."""
    return _lookup("craft essence", atlas.find_craft_essences(query), atlas.describe_craft_essence, query)


@mcp.tool()
def lookup_mystic_code(query: str) -> str:
    """Mystic Code skills with level 1~10 values and cooldowns. Query by name."""
    return _lookup("mystic code", atlas.find_mystic_codes(query), atlas.describe_mystic_code, query)


@mcp.tool()
def lookup_command_code(query: str) -> str:
    """Command Code effects. Query by English name, Japanese name, or collection number."""
    return _lookup("command code", atlas.find_command_codes(query), atlas.describe_command_code, query)


@mcp.tool()
def find_quest(name: str) -> str:
    """Find quests by their Japanese name as shown in game (partial names work).
    Returns ids and phases to pass to `prepare_battle`."""
    quests = atlas.search_quests(name)
    if not quests:
        return f"no quest matches {name!r}"
    note = ""
    if quests[0].get("fuzzy"):
        note = (f"Nothing contains {name!r}; these are only similar names. Check one matches the "
                "screen before using it.\n")
    return note + "\n".join(
        f"id {q['id']} phases {q['phases']} (enemy data: {q['phasesWithEnemies'] or 'none'}): "
        f"{q['originalName']} / {q['name']} | {q['war']} | {q['spot']} | AP {q['consume']}"
        for q in quests
    )


@mcp.tool()
def prepare_battle(
    quest_id: int, phase: int, party: list[str], ces: list[str] | None = None, mystic_code: str | None = None
) -> str:
    """Load the battle brief: every wave's enemies (class, HP, traits, skills, NP, damage
    multipliers against your party) plus your party's full kits. `party` holds servant names
    or collection numbers, frontline first, support servant included. `ces` lines up with
    `party` (use "" for no CE). Kept for `battle_brief`."""
    global _brief
    members = []
    unknown = []
    for name in party:
        found = atlas.find_servants(name, limit=1)
        (members if found else unknown).append(found[0] if found else name)
    equipped = []
    for name in ces or []:
        found = atlas.find_craft_essences(name, limit=1) if name else []
        equipped.append(found[0] if found else None)
        if name and not found:
            unknown.append(name)
    mc = None
    if mystic_code:
        found = atlas.find_mystic_codes(mystic_code, limit=1)
        mc = found[0] if found else None
        if not found:
            unknown.append(mystic_code)
    _brief = atlas.battle_brief(quest_id, phase, members, equipped, mc)
    yours = [f"#{m['collectionNo']} {m['name']}: {memory.format_entry(e)}"
             for m in members if (e := memory.owned(m["collectionNo"]))]
    if yours:
        _brief += "\n\nYour copies (from the roster; supports may differ):\n" + "\n".join(yours)
    if unknown:
        _brief += f"\n\nNot found: {', '.join(unknown)}"
    return _brief


@mcp.tool()
def battle_brief() -> str:
    """Re-read the brief stored by the last `prepare_battle`."""
    return _brief or "no brief loaded, call prepare_battle first"


@mcp.tool()
def estimate_np_damage(
    servant: str,
    enemy_class: str,
    enemy_attribute: str,
    np_level: int | None = None,
    level: int | None = None,
    overcharge: int = 1,
    atk_up: float = 0,
    card_up: float = 0,
    np_up: float = 0,
    def_down: float = 0,
    power_up: float = 0,
    special: bool = False,
    atk_down: float = 0,
    extra_atk: int | None = None,
    ratio: float = 1.0,
    enemy_hp: int | None = None,
) -> str:
    """Estimate one NP's damage before spending resources: is this NP alone enough for the bar?
    Buffs are percentages summed from everything active (30 = +30%): atk_up (ATK up), card_up
    (Buster/Arts/Quick up for the NP's card type), np_up (NP damage up), def_down (enemy DEF
    down), power_up (trait-specific damage up). atk_down is ATK down on your servant (boss
    debuffs). special=True when the NP's special damage applies to this enemy.
    Level, NP level, NP version, Fou and CE come from the roster (else max level, NP1, newest
    NP, 1000 Fou, no CE); extra_atk overrides Fou + CE ATK. ratio is the calibration from this
    fight: real HP drop of an earlier NP divided by its estimate. enemy_class and
    enemy_attribute come from prepare_battle (e.g. "saber"/"human"). Ignores crits, cards, and
    enemy damage cut or special defenses; read those off the boss's status and leave margin."""
    matches = atlas.find_servants(servant, limit=1)
    if not matches:
        return f"no servant matches {servant!r}"
    s = matches[0]
    mine = memory.owned(s["collectionNo"]) or {}
    lvl = level or mine.get("level") or s["lvMax"]
    npl = np_level or mine.get("np") or 1
    if extra_atk is None:
        extra_atk, atk_from = _extra_atk(mine)
    else:
        atk_from = "given"
    try:
        r = atlas.np_damage(s, npl, lvl, overcharge, enemy_class, enemy_attribute, atk_up, card_up, np_up,
                            def_down, power_up, special, extra_atk, atk_down, mine.get("np_version"), ratio)
    except ValueError as e:
        return str(e)
    text = (f"#{s['collectionNo']} {s['name']} Lv{lvl} NP{npl} OC{overcharge}: {r['np']} "
            f"[{r['card']}, {r['hits']} hits, {r['np_percent']:g}%]\n"
            f"damage {r['min']:,} to {r['max']:,} (avg {r['avg']:,})"
            + (f", calibrated x{ratio:g}" if ratio != 1 else "") + "\n"
            f"extra ATK {extra_atk:,} ({atk_from}), "
            f"ATK {r['atk']:,}, class rate x{r['class_rate']:g}, vs {enemy_class} x{r['triangle']:g}, "
            f"attribute x{r['attribute']:g}, special x{r['special']:g}")
    if r["has_special"] and not special:
        text += "\nThis NP has special damage; pass special=True if it applies to this enemy."
    if enemy_hp:
        verdict = ("kills even on a low roll" if r["min"] >= enemy_hp
                   else "kills only on a good roll" if r["max"] >= enemy_hp
                   else f"leaves {enemy_hp - r['max']:,}+ HP")
        text += f"\nvs {enemy_hp:,} HP: {verdict}"
    return text


def _extra_atk(mine: dict) -> tuple[int, str]:
    """Fou + CE ATK for a roster entry, and where the numbers came from."""
    fou = mine.get("fou")
    parts = [f"Fou {fou}" if fou is not None else "Fou 1000 assumed"]
    total = 1000 if fou is None else fou
    if mine.get("ce"):
        ces = atlas.find_craft_essences(mine["ce"], limit=1)
        if ces:
            c = ces[0]
            lvl = (memory.owned_ce(c["collectionNo"]) or {}).get("level")
            atk = c["atkGrowth"][min(lvl or c["lvMax"], len(c["atkGrowth"])) - 1]
            total += atk
            parts.append(f"{c['name']} {atk}" + ("" if lvl else " at max level, assumed"))
    return total, " + ".join(parts)


@mcp.tool()
def read_notes(topic: str | None = None) -> str:
    """Your notes from earlier sessions. Without a topic: the list of topics with their first
    line. With a topic: that note in full."""
    return memory.read_notes(topic)


@mcp.tool()
def write_note(topic: str, text: str, replace: bool = False) -> str:
    """Save something worth knowing next session, under a short topic name, for example
    "ui" (how menus behave, where buttons are), "account" (mystic codes, command spells,
    progress), or "battle-<quest>" (party, turn plan, what worked, what went wrong). Appends
    a dated entry; replace=True rewrites the whole topic (use it to keep a topic tidy)."""
    return memory.write_note(topic, text, replace)


@mcp.tool()
def update_servant(
    servant: str,
    level: int | None = None,
    np: int | None = None,
    skills: list[int] | None = None,
    appends: list[int] | None = None,
    ascension: int | None = None,
    bond: int | None = None,
    grand: bool | None = None,
    ce: str | None = None,
    fou: int | None = None,
    np_version: str | None = None,
    note: str | None = None,
) -> str:
    """Record one of the user's own servants (not supports) as read from its details screen.
    `servant` is a name or collection number; only the fields you pass change. skills/appends
    are levels in slot order, e.g. [10, 10, 9]. ce is the equipped craft essence. fou is the
    ATK Fou bonus (e.g. 1000, 2000). np_version is the NP name the game shows, when the
    servant has several versions (e.g. "Rayproof Kyrielight")."""
    return memory.update_servant(servant, level=level, np=np, skills=skills, appends=appends,
                                 ascension=ascension, bond=bond, grand=grand, ce=ce, fou=fou,
                                 np_version=np_version, note=note)


@mcp.tool()
def roster(query: str | None = None, class_name: str | None = None) -> str:
    """The user's servants (synced from the game), with level, NP, skills, appends, ascension,
    grails, Fou, bond and Grand. Filter by a name fragment or a class (saber, archer, ...,
    shielder, ruler, avenger, moonCancer, ...)."""
    return memory.roster(query, class_name)


@mcp.tool()
def find_owned(effect: str, target: str | None = None, class_name: str | None = None) -> str:
    """Which of the user's servants can do something: searches every owned servant's skills
    and NP for an effect, e.g. "NP Seal", "Drain enemy charge", "Remove effects", "Ignore
    Invincible", "Taunt", "Charge NP", "Anti-Purge". `target` narrows by who it hits ("enemies",
    "all allies", "self"); `class_name` by class. Use it when building a party for a mechanic."""
    return account.find_owned(effect, target, class_name)


@mcp.tool()
def account_summary() -> str:
    """The user's account from the last sync: master level, AP max, cost cap, QP, Saint Quartz
    (never spend), when command spells come back, mystic codes with levels."""
    return account.summary()


@mcp.tool()
def inventory(item: str | None = None) -> str:
    """Item counts from the last sync. With a name (English or Japanese, part is enough):
    that item. Without: every material used for ascension and skills, plus apples."""
    return account.inventory(item)


@mcp.tool()
def update_ce(ce: str, level: int | None = None, mlb: bool | None = None, count: int | None = None,
              note: str | None = None) -> str:
    """Record a craft essence the user owns: level, whether it is max limit broken, how many
    copies. `ce` is a name or collection number; only the fields you pass change."""
    return memory.update_ce(ce, level=level, mlb=mlb, count=count, note=note)


@mcp.tool()
def list_ces(query: str | None = None) -> str:
    """The user's craft essences recorded so far. Use lookup_ce for what one does."""
    return memory.list_ces(query)


@mcp.tool()
def zoom(x: int, y: int, width: int, height: int) -> list:
    """Enlarged crop of the current screen, for small text and icons: NP %, buff icons, skill
    cooldown numbers, card labels, JP menu text. Coordinates are screenshot pixels (1280x720)."""
    image = device().screenshot()
    x, y = max(0, x), max(0, y)
    crop = image[y : y + height, x : x + width]
    if crop.size == 0:
        raise ValueError("the region is outside the 1280x720 screen")
    scale = max(1.0, min(4.0, 1280 / crop.shape[1], 720 / crop.shape[0]))
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return [f"crop ({x},{y}) {width}x{height}, enlarged x{scale:.1f}", Image(data=encode_jpeg(crop, 92), format="jpeg")]


PLANNER_PROMPT = """\
You are the battle planner for an agent playing Fate/Grand Order (JP) on the user's account.
You have fresh context and read-only tools: look and zoom at the game, battle_brief or
prepare_battle for the quest, the roster, CEs, notes (read battle-* and ui notes), lookups, and
estimate_np_damage. You cannot act in the game.

Request from the playing agent:
{request}

Current state: {state}
Current goal: {goal}

Produce a plan the playing agent can follow:
- Per HP bar / wave: which NPs, which skills (FGA notation: a b c / d e f / g h i, ally target
  digit after, j k l master skills, t1-t3 enemy target, x<front><back> order change), and what
  to keep for later bars. Spend only what each bar needs; check that with estimate_np_damage
  and say how sure you are.
- The turns where the boss is dangerous and how to survive them (invincibility, taunt, damage
  cut, Grand no-chain invincibility).
- Facts you relied on (from the screen or game data) separately from assumptions.
Plan without command spells. If the fight looks unwinnable without one, name the turn and why.
Keep it under 400 words. Plain text."""


@mcp.tool()
def plan_battle(request: str) -> str:
    """Ask a fresh battle planner (a separate Claude with read-only access: look, zoom, brief,
    roster, notes, lookups, damage estimates) for a plan per HP bar. Use it before a hard fight
    and after each bar break, with a request like "plan bar 2: boss 917k HP, everyone at 0% NP,
    Jeanne buff-blocked". Takes a minute or two and costs extra, so not for easy quests."""
    state = bridge().call("screen")
    if state["screen"] == "battle":
        state["battle"] = bridge().call("battle")["battle"]
    prompt = PLANNER_PROMPT.format(request=request, state=json.dumps(state), goal=memory.goal() or "none")
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--tools", "", "--mcp-config", str(PROJECT / "planner.mcp.json"),
             "--strict-mcp-config", "--allowedTools", "mcp__fgo-plan__*", "--output-format", "json"],
            capture_output=True, text=True, timeout=1200, cwd=PROJECT)
    except subprocess.TimeoutExpired:
        return ("planner ran out of time (20 min) and its work is lost. Ask a narrower question: one "
                "bar or one decision at a time, with the facts it needs in the request.")
    try:
        out = json.loads(result.stdout)
    except json.JSONDecodeError:
        return f"planner failed (exit {result.returncode}): {result.stderr[-500:] or result.stdout[-500:]}"
    cost = out.get("total_cost_usd")
    return f"{out.get('result', '')}\n\n(planner: {out.get('num_turns')} turns, ${cost:.2f})" if cost else out.get("result", "")


def run() -> None:
    mcp.run("stdio")


def run_planner() -> None:
    """The planner's MCP server: the same functions, read-only ones only."""
    planner = MCPServer("fgo-plan", instructions="Read-only tools for planning FGO battles. You cannot act in the game.")
    for tool in (look, zoom, battle_brief, prepare_battle, find_quest, roster, find_owned, account_summary, inventory, list_ces, read_notes,
                 lookup_servant, lookup_ce, lookup_mystic_code, lookup_command_code, estimate_np_damage):
        planner.tool()(tool)
    planner.run("stdio")
