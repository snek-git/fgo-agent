"""MCP server that lets an AI agent see and play FGO in the redroid container.

Battle mechanics (when the game is ready, casting, targeting, cards, the screens between turns)
run in FGA's own code through the bridge. The agent makes every decision.
"""

import json
import time

from mcp.server.mcpserver import Image, MCPServer

from . import atlas, memory
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
You keep memory between sessions: start every session with `read_notes`, and check `roster`
and `list_ces` before building a party. Record what you learn as you go: servant and CE
details whenever you open them (`update_servant`, `update_ce`), and lessons, UI quirks and
battle results in notes (`write_note`).
Apples may be used to refill AP. Never spend Saint Quartz (聖晶石), summon, or buy anything
unless the user told you to."""

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


def _view(state: dict | None = None) -> list:
    state = dict(state or {})
    if "screen" not in state:
        state["screen"] = bridge().call("screen")["screen"]
    if state["screen"] == "battle" and "battle" not in state:
        state["battle"] = bridge().call("battle")["battle"]
    if _brief and state["screen"] == "battle":
        state["brief"] = "battle brief loaded, call battle_brief to re-read it"
    image = device().screenshot()
    return [json.dumps(state), Image(data=encode_jpeg(image), format="jpeg")]


@mcp.tool()
def look() -> list:
    """Screenshot plus FGA's reading of which screen is up (battle, menu, support, repeat,
    ap_refill, withdraw, ...; "unknown" when none of FGA's detectors match). In battle it
    adds the wave, the turn within that wave, and which party member (1-6) is in each field
    slot (1-3)."""
    return _view()


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
    note: str | None = None,
) -> str:
    """Record one of the user's own servants (not supports) as read from its details screen.
    `servant` is a name or collection number; only the fields you pass change. skills/appends
    are levels in slot order, e.g. [10, 10, 9]. ce is the equipped craft essence."""
    return memory.update_servant(servant, level=level, np=np, skills=skills, appends=appends,
                                 ascension=ascension, bond=bond, grand=grand, ce=ce, note=note)


@mcp.tool()
def roster(query: str | None = None, class_name: str | None = None) -> str:
    """The user's servants recorded so far, with levels, NP, skills, appends and bond. Filter by
    a name fragment or a class (saber, archer, ..., shielder, ruler, avenger, moonCancer, ...)."""
    return memory.roster(query, class_name)


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


def run() -> None:
    mcp.run("stdio")
