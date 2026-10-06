"""Screen locations, ported from FGA's locations/*.kt (16:9, not wide).

FGA writes coordinates in a 2560x1440 script space with helpers xFromCenter / xFromRight /
yFromBottom. The container runs at 1280x720, so every value is halved here.
"""

from .vision import Region

W, H = 2560, 1440
CX = W // 2


def at(x: int, y: int) -> tuple[int, int]:
    return round(x / 2), round(y / 2)


def area(x: int, y: int, w: int, h: int) -> Region:
    return round(x / 2), round(y / 2), round(w / 2), round(h / 2)


# --- battle command screen (BattleScreenLocations.kt) ---
BATTLE_CHECK = area(W - 455, H - 181, 336, 116)  # battle.png = waiting for orders
ATTACK = at(W - 260, H - 240)
SKILL_OK = at(CX + 400, 850)
SKILL_USE_CHECK = area(CX - 210, 320, 420, 85)  # skill_use.png = "use this skill?" dialog
SAFE_MIDDLE = at(CX, 550)
SKILL_X = (148, 324, 500, 784, 960, 1136, 1418, 1594, 1770)
SKILL_Y = 1158


def skill(servant: int, slot: int) -> tuple[int, int]:
    """servant 1-3 (left to right), slot 1-3."""
    return at(SKILL_X[(servant - 1) * 3 + (slot - 1)], SKILL_Y)


def servant_target(servant: int) -> tuple[int, int]:
    return at(CX + (-580, 0, 660)[servant - 1], 880)


def enemy_target(enemy: int) -> tuple[int, int]:
    """enemy 1-3, left to right as shown on screen."""
    return at((90, 570, 1050)[enemy - 1], 80)


def servant_present(servant: int) -> Region:
    sx, sy = SKILL_X[(servant - 1) * 3 + 2], SKILL_Y
    return area(sx + 35, sy + 67, 120, 120)


# Master skill x positions are relative to the battle_menu.png button (MasterLocations.kt).
MASTER_MENU_SEARCH = area(W - 400, 360, 400, 80)
MASTER_MENU_DEFAULT_X = W - 298


def master_skill(skill_no: int, menu_x_script: int) -> tuple[int, int]:
    return at((-740, -560, -400)[skill_no - 1] + 178 + menu_x_script, 620)


def master_open(menu_x_script: int) -> tuple[int, int]:
    return at(menu_x_script, 640)


# --- card selection (AttackScreenLocations.kt) ---
CARD_X = (-980, -530, 20, 520, 1070)
NP_CLICK = ((-280, 220), (20, 400), (460, 400))
CARD_BACK = at(W - 160, 1370)


def card(n: int) -> tuple[int, int]:
    return at(CX + CARD_X[n - 1], 1000)


def np_card(servant: int) -> tuple[int, int]:
    x, y = NP_CLICK[servant - 1]
    return at(CX + x, y)


def card_type_region(n: int) -> Region:
    return area(CX + (-1280, -768, -256, 256, 768)[n - 1], 1060, 512, 200)


def card_affinity_region(n: int) -> Region:
    return area(CX + (-985, -470, 41, 554, 1068)[n - 1], 590, 250, 260)


def card_stun_region(n: int) -> Region:
    return area(CX + (-1280, -768, -256, 256, 768)[n - 1], 930, 248, 188)


# --- menus and results (Locations.kt, SupportScreenLocations.kt) ---
MENU_CHECK = area(W - 460, 1200, 460, 240)  # menu.png = quest list
MENU_FIRST_QUEST = at(W - 270, 440)
START_QUEST = at(W - 160, H - 90)
SUPPORT_CHECK = area(0, 0, 200, 400)  # support_screen.png
FIRST_SUPPORT = at(CX, 500)
STORY_SKIP_CHECK = area(CX + 960, 20, 300, 120)
STORY_SKIP = at(CX + 1080, 80)
STORY_SKIP_YES = at(CX + 320, 1100)
STAMINA_CHECK = area(CX - 680, 200, 300, 300)
STAMINA_CLOSE = at(CX, 1240)
RESULT_CHECK = area(CX - 1180, 300, 700, 200)
RESULT_MASTER_EXP = area(CX, 350, 400, 110)
RESULT_MASTER_LVL = area(CX + 710, 160, 250, 270)
RESULT_BOND = area(CX + 720, 600, 120, 400)
RESULT_CLICK = at(CX + 320, 1350)
QUEST_REWARD_CHECK = area(CX + 350, 140, 370, 250)
REPEAT_CHECK = area(CX + 120, 1000, 800, 300)
WITHDRAW_CHECK = area(CX - 880, 540, 1800, 333)
NP_STARTED = area(CX - 400, 500, 800, 400)
MIDDLE = at(CX, 720)
