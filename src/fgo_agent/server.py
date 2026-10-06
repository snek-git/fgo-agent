"""MCP server that lets an AI agent see and play FGO in the redroid container."""

import json
import time

from mcp.server.mcpserver import Image, MCPServer

from . import atlas
from . import locations as L
from .game import Game, encode_jpeg

INSTRUCTIONS = """\
You are playing Fate/Grand Order (JP) on an Android container. The screen is 1280x720 and
every x,y in these tools uses those pixels, so read positions straight off the screenshot.
Start with `look`. In battle prefer the battle tools over raw taps: they know where skills,
targets and cards are. Use raw `tap` for menus, story and anything else.
Servants, skill slots, enemies and cards are numbered left to right from 1.
Before starting a quest, read its Japanese name off the screen, call `find_quest`, then
`prepare_battle` with the quest id and your party so you know every wave's enemies and your
own kit. `lookup_servant` gives any servant's skills, NP and deck.
Never spend Saint Quartz, buy anything, or summon unless the user told you to."""

mcp = MCPServer("fgo", instructions=INSTRUCTIONS)
_game: Game | None = None
_brief: str | None = None


def game() -> Game:
    global _game
    if _game is None:
        _game = Game()
    return _game


def _view(note: str | None = None) -> list:
    state, image = game().observe()
    if note:
        state["note"] = note
    if _brief and state["screen"] in ("battle_command", "card_select"):
        state["brief"] = "battle brief loaded, call battle_brief to re-read it"
    return [json.dumps(state), Image(data=encode_jpeg(image), format="jpeg")]


@mcp.tool()
def look() -> list:
    """Screenshot plus parsed state: which screen is up, servants on field, and card
    types and affinity while on the card screen."""
    return _view()


@mcp.tool()
def tap(x: int, y: int, wait: float = 1.0) -> list:
    """Tap at screen pixel (x, y), wait `wait` seconds, then return a fresh look."""
    game().device.tap(x, y)
    time.sleep(wait)
    return _view()


@mcp.tool()
def swipe(x1: int, y1: int, x2: int, y2: int, ms: int = 400, wait: float = 1.0) -> list:
    """Swipe between two screen pixels (scroll lists), then return a fresh look."""
    game().device.swipe(x1, y1, x2, y2, ms)
    time.sleep(wait)
    return _view()


@mcp.tool()
def back(wait: float = 1.0) -> list:
    """Press Android back, then return a fresh look."""
    game().device.back()
    time.sleep(wait)
    return _view()


@mcp.tool()
def wait(seconds: float = 3.0) -> list:
    """Do nothing for a while (loading, animations, max 60s), then return a fresh look."""
    time.sleep(min(seconds, 60))
    return _view()


@mcp.tool()
def launch_fgo() -> list:
    """Start the FGO app if it is not running."""
    if not game().device.fgo_running():
        game().device.launch_fgo()
        time.sleep(8)
    return _view()


@mcp.tool()
def use_skill(servant: int, skill: int, target: int | None = None) -> list:
    """Battle: use servant (1-3) skill (1-3). Pass target (1-3) for skills aimed at one ally."""
    return _view(f"screen after skill: {game().use_skill(servant, skill, target)}")


@mcp.tool()
def use_master_skill(skill: int, target: int | None = None) -> list:
    """Battle: use mystic code skill (1-3), with optional ally target (1-3)."""
    return _view(f"screen after master skill: {game().use_master_skill(skill, target)}")


@mcp.tool()
def target_enemy(enemy: int) -> list:
    """Battle: focus enemy 1-3 (left to right) before attacking."""
    game().target_enemy(enemy)
    return _view()


@mcp.tool()
def open_cards() -> list:
    """Battle: tap Attack to open card selection. The returned state lists card types and
    affinity. Then call `play_cards`, or `close_cards` to go back for more skills."""
    game().device.tap(*L.ATTACK)
    game().wait_for({"card_select"}, timeout=10)
    time.sleep(0.4)
    return _view()


@mcp.tool()
def play_cards(cards: list[str]) -> list:
    """Battle: on the open card screen, play three picks in order, e.g. ["np1", "3", "5"].
    Face cards are "1".."5" left to right, noble phantasms "np1".."np3" by servant.
    Waits until the turn resolves (up to 90s)."""
    if len(cards) != 3:
        raise ValueError("pick exactly 3 cards")
    return _view(f"screen after attack: {game().play_cards(cards)}")


@mcp.tool()
def close_cards() -> list:
    """Battle: leave the card screen back to the command screen."""
    game().device.tap(*L.CARD_BACK)
    time.sleep(0.8)
    return _view()


@mcp.tool()
def advance_results() -> list:
    """After a quest: tap through bond, exp and drop screens until something else shows."""
    return _view(f"stopped on: {game().advance_results()}")


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
    rows = atlas.search_quests(name)
    if not rows:
        return f"no quest matches {name!r}"
    quests: dict[int, dict] = {}
    for r in rows:
        quests.setdefault(r["id"], {**r, "phases": []})["phases"].append(r["phase"])
    return "\n".join(
        f"id {q['id']} phases {q['phases']}: {q['name'].replace(chr(10), ' ')} | {q.get('spotName', '')} | AP {q.get('consume', '?')}"
        for q in list(quests.values())[:25]
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
    if unknown:
        _brief += f"\n\nNot found: {', '.join(unknown)}"
    return _brief


@mcp.tool()
def battle_brief() -> str:
    """Re-read the brief stored by the last `prepare_battle`."""
    return _brief or "no brief loaded, call prepare_battle first"


def run() -> None:
    mcp.run("stdio")
