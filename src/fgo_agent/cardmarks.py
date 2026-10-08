"""Which command cards carry the support's "+SUPPORT" label, read straight from the screenshot.

FGA's parser looks for the label's left end ("+SU", support.png), which the row of buff icons
above a card often covers; its owner field is then wrong for the support's cards. Checking the
right end ("PPORT", cut from a real card screen) as well catches most of those. Regions are
FGA's AttackScreenLocations.supportCheckRegion, scaled to the 1280x720 screenshot.
"""

from functools import cache
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CARD_X = (-985, -470, 41, 554, 1068)  # FGA's affinityRegion x per card, from the screen centre at 2560 wide
THRESHOLD = 0.8


@cache
def _templates() -> list[np.ndarray]:
    return [cv2.imread(str(ROOT / "vendor/FGA/app/src/main/assets/Jp/support.png")),
            cv2.imread(str(Path(__file__).with_name("assets") / "support_port.png"))]


def support_cards(screen: np.ndarray) -> list[bool]:
    """For cards 1-5 on the card screen: does it carry the support label?"""
    marks = []
    for x in CARD_X:
        left = (1280 + x - 50) // 2
        region = screen[345:475, left:left + 125]
        marks.append(any(float(cv2.matchTemplate(region, t, cv2.TM_CCOEFF_NORMED).max()) >= THRESHOLD
                         for t in _templates()))
    return marks
