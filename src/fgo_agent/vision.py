"""Template matching against FGA's 720p templates (assets/, MIT, see assets/FGA-LICENSE)."""

from functools import cache
from pathlib import Path

import cv2
import numpy as np

ASSETS = Path(__file__).parent / "assets"
# JP-specific templates override the EN ones, like FGA does for its JP server.
SEARCH_ORDER = ("Jp", "En")
MIN_SIMILARITY = 0.8

Region = tuple[int, int, int, int]  # x, y, w, h in screen pixels


@cache
def template(name: str) -> np.ndarray:
    for folder in SEARCH_ORDER:
        path = ASSETS / folder / name
        if path.exists():
            return cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    raise FileNotFoundError(name)


def gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def score(screen_gray: np.ndarray, name: str, region: Region) -> float:
    x, y, w, h = region
    crop = screen_gray[max(y, 0) : y + h, max(x, 0) : x + w]
    needle = template(name)
    if crop.shape[0] < needle.shape[0] or crop.shape[1] < needle.shape[1]:
        return 0.0
    return float(cv2.matchTemplate(crop, needle, cv2.TM_CCOEFF_NORMED).max())


def find(screen_gray: np.ndarray, name: str, region: Region, similarity: float = MIN_SIMILARITY):
    """Center of the best match in screen pixels, or None."""
    x, y, w, h = region
    crop = screen_gray[max(y, 0) : y + h, max(x, 0) : x + w]
    needle = template(name)
    if crop.shape[0] < needle.shape[0] or crop.shape[1] < needle.shape[1]:
        return None
    result = cv2.matchTemplate(crop, needle, cv2.TM_CCOEFF_NORMED)
    _, best, _, (bx, by) = cv2.minMaxLoc(result)
    if best < similarity:
        return None
    return (max(x, 0) + bx + needle.shape[1] // 2, max(y, 0) + by + needle.shape[0] // 2)


def exists(screen_gray: np.ndarray, name: str, region: Region, similarity: float = MIN_SIMILARITY) -> bool:
    return score(screen_gray, name, region) >= similarity


def is_black(screen_gray: np.ndarray, region: Region) -> bool:
    x, y, w, h = region
    return float(screen_gray[y : y + h, x : x + w].mean()) < 10
