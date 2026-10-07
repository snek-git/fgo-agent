"""Live viewer: the game screen with the playing Claude session's feed underneath.

The feed comes from Claude Code's own session transcript for this project directory (written
by both interactive and headless runs), so it works however the session was started.
"""

import asyncio
import json
import queue
import re
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, StreamingResponse
from starlette.routing import Route

from . import stream


PROJECT = Path(__file__).resolve().parents[2]
TRANSCRIPTS = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(PROJECT))
HISTORY = 200  # events replayed to a page that connects mid-session

video = stream.Video()
audio = stream.Audio()


async def mjpeg(request: Request) -> StreamingResponse:
    async def frames():
        video.join()
        try:
            seen = -1
            while not await request.is_disconnected():
                if video.seq != seen and video.frame is not None:
                    seen = video.seq
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + video.frame + b"\r\n"
                await asyncio.sleep(1 / 120)
        finally:
            video.leave()

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


async def mp3(request: Request) -> StreamingResponse:
    async def chunks():
        q = audio.subscribe()
        try:
            while not await request.is_disconnected():
                try:
                    yield await asyncio.to_thread(q.get, True, 1.0)
                except queue.Empty:
                    continue
        finally:
            audio.unsubscribe(q)

    return StreamingResponse(chunks(), media_type="audio/mpeg", headers={"Cache-Control": "no-cache"})


def _tool_name(name: str) -> str:
    return name.removeprefix("mcp__fgo__")


def parse(entry: dict) -> list[dict]:
    """Transcript line -> feed events."""
    kind = entry.get("type")
    stamp = entry.get("timestamp", "")
    content = entry.get("message", {}).get("content")
    events = []
    if kind == "user" and isinstance(content, str):
        events.append({"kind": "prompt", "text": content, "time": stamp})
    elif kind == "assistant" and isinstance(content, list):
        for part in content:
            if part["type"] == "text" and part["text"].strip():
                events.append({"kind": "say", "text": part["text"].strip(), "time": stamp})
            elif part["type"] == "thinking" and part.get("thinking", "").strip():
                events.append({"kind": "think", "text": part["thinking"].strip(), "time": stamp})
            elif part["type"] == "tool_use":
                events.append({"kind": "call", "id": part["id"], "tool": _tool_name(part["name"]),
                               "args": part["input"], "time": stamp})
    elif kind == "user" and isinstance(content, list):
        for part in content:
            if part.get("type") == "text" and part["text"].strip():
                events.append({"kind": "prompt", "text": part["text"], "time": stamp})
            if part.get("type") != "tool_result":
                continue
            items = part["content"] if isinstance(part["content"], list) else [{"type": "text", "text": str(part["content"])}]
            texts = [i["text"] for i in items if i.get("type") == "text"
                     and not i["text"].startswith("[Image: source: ")]  # Claude Code's path to the image
            text = "\n".join(texts)
            try:  # plain-string tool results arrive wrapped as {"result": "..."}
                wrapped = json.loads(text)
                if isinstance(wrapped, dict) and list(wrapped) == ["result"]:
                    text = wrapped["result"]
            except json.JSONDecodeError:
                pass
            image = next((i["source"]["data"] for i in items if i.get("type") == "image"), None)
            events.append({"kind": "result", "id": part["tool_use_id"], "text": text, "image": image,
                           "error": bool(part.get("is_error")), "time": stamp})
    elif kind == "cost-state":
        events.append({"kind": "cost", "usd": entry.get("totalCostUSD")})
    return events


def latest_transcript() -> Path | None:
    files = list(TRANSCRIPTS.glob("*.jsonl"))
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


async def feed(request: Request) -> StreamingResponse:
    async def stream():
        current: Path | None = None
        handle = None
        try:
            while not await request.is_disconnected():
                newest = latest_transcript()
                if newest is not None and newest != current:
                    # A new session started: replay its recent history, then follow it
                    if handle:
                        handle.close()
                    current, handle = newest, newest.open()
                    history = [e for line in handle for e in parse(_load(line))][-HISTORY:]
                    yield _sse({"kind": "session", "id": current.stem})
                    for event in history:
                        yield _sse(event)
                if handle:
                    for line in handle:
                        for event in parse(_load(line)):
                            yield _sse(event)
                await asyncio.sleep(0.4)
        finally:
            if handle:
                handle.close()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _load(line: str) -> dict:
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def page(_: Request) -> HTMLResponse:
    return HTMLResponse((Path(__file__).parent / "view.html").read_text())


app = Starlette(routes=[Route("/", page), Route("/screen.mjpg", mjpeg), Route("/audio.mp3", mp3),
                        Route("/feed", feed)])


def run(host: str, port: int) -> None:
    print(f"viewer on http://{host}:{port}  (transcripts: {TRANSCRIPTS})")
    uvicorn.run(app, host=host, port=port, log_level="warning")
