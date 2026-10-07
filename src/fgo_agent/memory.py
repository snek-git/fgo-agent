"""What the agent keeps between sessions: free-form notes and a roster of the user's servants.

Both are plain files under data/ (notes/<topic>.md, roster.json) so the user can read and edit
them too. data/ is the user's account data and stays out of git.
"""

import json
import re
import time
from pathlib import Path

from . import atlas

DATA = Path(__file__).resolve().parents[2] / "data"
NOTES = DATA / "notes"
ROSTER = DATA / "roster.json"


# --- notes ---

def _topic_path(topic: str) -> Path:
    slug = re.sub(r"[^\w-]+", "-", topic.strip().lower()).strip("-")
    if not slug:
        raise ValueError("topic is empty")
    return NOTES / f"{slug}.md"


def read_notes(topic: str | None = None) -> str:
    if topic:
        path = _topic_path(topic)
        return path.read_text() if path.exists() else f"no notes on {topic!r} yet"
    topics = sorted(NOTES.glob("*.md")) if NOTES.exists() else []
    if not topics:
        return "no notes yet"
    lines = []
    for path in topics:
        text = path.read_text()
        first = next((l for l in text.splitlines() if l.strip()), "")
        lines.append(f"- {path.stem} ({len(text)} chars): {first[:100]}")
    return "Topics (read one with read_notes(topic)):\n" + "\n".join(lines)


def write_note(topic: str, text: str, replace: bool = False) -> str:
    path = _topic_path(topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    if replace or not path.exists():
        path.write_text(text.rstrip() + "\n")
    else:
        with path.open("a") as f:
            f.write(f"\n## {time.strftime('%Y-%m-%d %H:%M')}\n{text.rstrip()}\n")
    return f"saved to notes/{path.name}"


# --- current goal ---

GOAL = DATA / "goal.txt"


def goal() -> str:
    return GOAL.read_text().strip() if GOAL.exists() else ""


def set_goal(text: str) -> None:
    GOAL.parent.mkdir(parents=True, exist_ok=True)
    GOAL.write_text(text.strip() + "\n")


# --- roster ---

FIELDS = ("level", "np", "skills", "appends", "ascension", "bond", "grand", "ce", "note")


def _load() -> dict:
    return json.loads(ROSTER.read_text()) if ROSTER.exists() else {}


def _save(roster: dict) -> None:
    ROSTER.parent.mkdir(parents=True, exist_ok=True)
    ROSTER.write_text(json.dumps(roster, ensure_ascii=False, indent=2) + "\n")


def update_servant(servant: str, **fields) -> str:
    matches = atlas.find_servants(servant, limit=3)
    if not matches:
        return f"no servant matches {servant!r}; use the collection number"
    s = matches[0]
    roster = _load()
    entry = roster.get(str(s["collectionNo"]), {})
    entry.update({"name": s["name"], "class": s["className"], "rarity": s["rarity"]})
    entry.update({k: v for k, v in fields.items() if k in FIELDS and v is not None})
    entry["updated"] = time.strftime("%Y-%m-%d")
    roster[str(s["collectionNo"])] = entry
    _save(roster)
    text = f"saved #{s['collectionNo']} {s['name']} ({s['className']}): {format_entry(entry)}"
    if len(matches) > 1:
        others = ", ".join(f"#{m['collectionNo']} {m['name']} ({m['className']})" for m in matches[1:])
        text += f"\nOther matches for {servant!r}: {others}. Use the collection number if this was the wrong one."
    return text


def format_entry(e: dict) -> str:
    parts = []
    if "level" in e:
        parts.append(f"Lv{e['level']}")
    if "np" in e:
        parts.append(f"NP{e['np']}")
    if "skills" in e:
        parts.append("skills " + "/".join(map(str, e["skills"])))
    if "appends" in e:
        parts.append("appends " + "/".join(map(str, e["appends"])))
    if "ascension" in e:
        parts.append(f"asc {e['ascension']}")
    if "bond" in e:
        parts.append(f"bond {e['bond']}")
    if e.get("grand"):
        parts.append("GRAND")
    if e.get("ce"):
        parts.append(f"CE {e['ce']}")
    if e.get("note"):
        parts.append(f"({e['note']})")
    return " ".join(parts)


def roster(query: str | None = None, class_name: str | None = None) -> str:
    entries = _load()
    if not entries:
        return "roster is empty"
    rows = []
    for no, e in sorted(entries.items(), key=lambda kv: (kv[1].get("class", ""), -kv[1].get("rarity", 0), kv[1]["name"])):
        if class_name and e.get("class", "").lower() != class_name.lower():
            continue
        if query and query.lower() not in e["name"].lower() and query != no:
            continue
        rows.append(f"#{no} {e['name']} [{e.get('class')} {e.get('rarity')}*] {format_entry(e)}")
    return "\n".join(rows) if rows else "no roster entries match"


def owned(collection_no: int) -> dict | None:
    return _load().get(str(collection_no))


# --- craft essences ---

CES = DATA / "ces.json"
CE_FIELDS = ("level", "mlb", "count", "note")


def update_ce(ce: str, **fields) -> str:
    matches = atlas.find_craft_essences(ce, limit=3)
    if not matches:
        return f"no craft essence matches {ce!r}; use the collection number"
    c = matches[0]
    ces = json.loads(CES.read_text()) if CES.exists() else {}
    entry = ces.get(str(c["collectionNo"]), {})
    entry.update({"name": c["name"], "rarity": c["rarity"]})
    entry.update({k: v for k, v in fields.items() if k in CE_FIELDS and v is not None})
    entry["updated"] = time.strftime("%Y-%m-%d")
    ces[str(c["collectionNo"])] = entry
    CES.parent.mkdir(parents=True, exist_ok=True)
    CES.write_text(json.dumps(ces, ensure_ascii=False, indent=2) + "\n")
    text = f"saved CE #{c['collectionNo']} {c['name']}: {_format_ce(entry)}"
    if len(matches) > 1:
        others = ", ".join(f"#{m['collectionNo']} {m['name']}" for m in matches[1:])
        text += f"\nOther matches for {ce!r}: {others}. Use the collection number if this was the wrong one."
    return text


def _format_ce(e: dict) -> str:
    parts = [f"{e.get('rarity')}*"]
    if "level" in e:
        parts.append(f"Lv{e['level']}")
    if e.get("mlb"):
        parts.append("MLB")
    if "count" in e:
        parts.append(f"x{e['count']}")
    if e.get("note"):
        parts.append(f"({e['note']})")
    return " ".join(parts)


def list_ces(query: str | None = None) -> str:
    ces = json.loads(CES.read_text()) if CES.exists() else {}
    rows = [f"#{no} {e['name']} {_format_ce(e)}"
            for no, e in sorted(ces.items(), key=lambda kv: (-kv[1].get("rarity", 0), kv[1]["name"]))
            if not query or query.lower() in e["name"].lower() or query == no]
    return "\n".join(rows) if rows else ("no CEs recorded yet" if not ces else "no CEs match")
