"""MCP server that lets an AI agent see and play FGO in the redroid container."""

import json
import time

from mcp.server.mcpserver import Image, MCPServer

from . import locations as L
from .game import Game, encode_jpeg

INSTRUCTIONS = """\
You are playing Fate/Grand Order (JP) on an Android container. The screen is 1280x720 and
every x,y in these tools uses those pixels, so read positions straight off the screenshot.
Start with `look`. In battle prefer the battle tools over raw taps: they know where skills,
targets and cards are. Use raw `tap` for menus, story and anything else.
Servants, skill slots, enemies and cards are numbered left to right from 1.
Never spend Saint Quartz, buy anything, or summon unless the user told you to."""

mcp = MCPServer("fgo", instructions=INSTRUCTIONS)
_game: Game | None = None


def game() -> Game:
    global _game
    if _game is None:
        _game = Game()
    return _game


def _view(note: str | None = None) -> list:
    state, image = game().observe()
    if note:
        state["note"] = note
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


def run() -> None:
    mcp.run("stdio")
