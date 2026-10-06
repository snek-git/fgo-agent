"""FGO game layer: reads the screen into a state dict and runs battle actions.

Screen checks follow FGA's AutoBattle loop. The agent decides strategy; this layer only
knows where things are and whether a known screen is up.
"""

import time

import cv2
import numpy as np

from . import locations as L
from .device import Device
from .vision import exists, find, gray, is_black

CARD_TYPES = (("buster.png", "buster"), ("art.png", "arts"), ("quick.png", "quick"))
STUN_IMAGES = ("stun.png", "immobilized.png", "stun_buster.png", "stun_arts.png", "stun_quick.png")


class Game:
    def __init__(self, device: Device | None = None):
        self.device = device or Device()
        self.master_menu_x: int | None = None  # script space, found on first battle screen

    # --- reading ---

    def capture(self) -> tuple[np.ndarray, np.ndarray]:
        image = self.device.screenshot()
        return image, gray(image)

    def screen(self, g: np.ndarray) -> str:
        checks = (
            ("battle_command", lambda: exists(g, "battle.png", L.BATTLE_CHECK)),
            ("card_select", lambda: self._card_screen(g)),
            ("quest_menu", lambda: exists(g, "menu.png", L.MENU_CHECK)),
            ("support_select", lambda: exists(g, "support_screen.png", L.SUPPORT_CHECK)),
            ("result_bond", lambda: exists(g, "bond.png", L.RESULT_BOND)),
            ("result", lambda: exists(g, "result.png", L.RESULT_CHECK)
                or exists(g, "master_lvl_up.png", L.RESULT_MASTER_LVL)
                or exists(g, "master_exp.png", L.RESULT_MASTER_EXP)),
            ("quest_reward", lambda: exists(g, "questreward.png", L.QUEST_REWARD_CHECK)),
            ("repeat_prompt", lambda: exists(g, "repeat.png", L.REPEAT_CHECK)),
            ("withdraw_prompt", lambda: exists(g, "withdraw.png", L.WITHDRAW_CHECK)),
            ("stamina_refill", lambda: exists(g, "stamina.png", L.STAMINA_CHECK)),
            ("story_skippable", lambda: exists(g, "storyskip.png", L.STORY_SKIP_CHECK, similarity=0.7)),
            ("black_screen", lambda: is_black(g, L.NP_STARTED)),  # NP animation or loading
        )
        for name, check in checks:
            if check():
                return name
        return "unknown"

    def _card_screen(self, g: np.ndarray) -> bool:
        found = sum(
            any(exists(g, image, L.card_type_region(n)) for image, _ in CARD_TYPES) for n in (1, 2, 3, 4, 5)
        )
        return found >= 3

    def cards(self, g: np.ndarray) -> list[dict]:
        result = []
        for n in (1, 2, 3, 4, 5):
            stunned = any(exists(g, image, L.card_stun_region(n)) for image in STUN_IMAGES)
            kind = "unknown"
            if not stunned:
                kind = next((k for image, k in CARD_TYPES if exists(g, image, L.card_type_region(n))), "unknown")
            affinity = "normal"
            if exists(g, "weak.png", L.card_affinity_region(n)):
                affinity = "weak"
            elif exists(g, "resist.png", L.card_affinity_region(n)):
                affinity = "resist"
            result.append({"card": n, "type": kind, "affinity": affinity, "stunned": stunned})
        return result

    def servants_present(self, g: np.ndarray) -> list[int]:
        return [s for s in (1, 2, 3) if exists(g, "servant_exist.png", L.servant_present(s), similarity=0.7)]

    def observe(self) -> tuple[dict, np.ndarray]:
        image, g = self.capture()
        state: dict = {"screen": self.screen(g), "fgo_running": self.device.fgo_running()}
        if state["screen"] == "battle_command":
            self._locate_master_menu(g)
            state["servants_on_field"] = self.servants_present(g)
        if state["screen"] == "card_select":
            state["cards"] = self.cards(g)
        return state, image

    def _locate_master_menu(self, g: np.ndarray) -> None:
        hit = find(g, "battle_menu.png", L.MASTER_MENU_SEARCH)
        self.master_menu_x = hit[0] * 2 if hit else L.MASTER_MENU_DEFAULT_X

    def wait_for(self, screens: set[str], timeout: float = 30, poll: float = 0.5) -> str:
        end = time.monotonic() + timeout
        current = "unknown"
        while time.monotonic() < end:
            _, g = self.capture()
            current = self.screen(g)
            if current in screens:
                return current
            time.sleep(poll)
        return current

    # --- battle actions ---

    def _confirm_skill(self) -> None:
        """Tap OK on the "use this skill?" dialog, if the game shows it."""
        time.sleep(0.5)
        _, g = self.capture()
        if exists(g, "skill_use.png", L.SKILL_USE_CHECK):
            self.device.tap(*L.SKILL_OK)
            time.sleep(0.5)

    def use_skill(self, servant: int, slot: int, target: int | None = None) -> str:
        self.device.tap(*L.skill(servant, slot))
        self._confirm_skill()
        if target is not None:
            self.device.tap(*L.servant_target(target))
        return self.wait_for({"battle_command"}, timeout=15)

    def use_master_skill(self, skill_no: int, target: int | None = None) -> str:
        if self.master_menu_x is None:
            _, g = self.capture()
            self._locate_master_menu(g)
        self.device.tap(*L.master_open(self.master_menu_x))
        time.sleep(0.6)
        self.device.tap(*L.master_skill(skill_no, self.master_menu_x))
        self._confirm_skill()
        if target is not None:
            self.device.tap(*L.servant_target(target))
        return self.wait_for({"battle_command"}, timeout=15)

    def target_enemy(self, enemy: int) -> None:
        self.device.tap(*L.enemy_target(enemy))
        time.sleep(0.3)

    def play_cards(self, picks: list[str]) -> str:
        """picks like ["np1", "3", "1"]: cards 1-5 or np1-np3, in order. Card screen must be open."""
        for pick in picks:
            pick = pick.strip().lower()
            if pick.startswith("np"):
                self.device.tap(*L.np_card(int(pick[2:])))
            else:
                self.device.tap(*L.card(int(pick)))
            time.sleep(0.35)
        # FGO fires once three cards are chosen. Wait for the turn to resolve.
        return self.wait_for({"battle_command", "result", "result_bond", "quest_reward"}, timeout=90, poll=1.0)

    def skip_story(self) -> bool:
        """Tap SKIP and confirm, like FGA. False if no skip button is showing."""
        _, g = self.capture()
        if not exists(g, "storyskip.png", L.STORY_SKIP_CHECK, similarity=0.7):
            return False
        self.device.tap(*L.STORY_SKIP)
        time.sleep(0.5)
        self.device.tap(*L.STORY_SKIP_YES)
        time.sleep(1.5)
        return True

    def advance_results(self, max_taps: int = 25) -> str:
        """Tap through result / bond / exp / drop screens. Only starts from a detected result
        screen, so it never taps blind on menus that might spend something."""
        _, g = self.capture()
        current = self.screen(g)
        if current not in {"result", "result_bond", "quest_reward"}:
            return current
        for _ in range(max_taps):
            _, g = self.capture()
            current = self.screen(g)
            if current not in {"result", "result_bond", "quest_reward", "unknown", "black_screen"}:
                return current
            self.device.tap(*L.RESULT_CLICK)
            time.sleep(0.6)
        return current


def encode_jpeg(image: np.ndarray, quality: int = 85) -> bytes:
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return buf.tobytes()
