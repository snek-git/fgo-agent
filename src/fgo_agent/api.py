"""HTTP API behind the board: account to-do data, the task queue, and account sync.

The web board (/board) and the desktop app both use these routes, so they always agree.
Long jobs (the queue runner, a sync) run as user services so they outlive the request, the
page, and the server itself.
"""

import asyncio
import os
import subprocess
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from . import account, board, tasks

PROJECT = Path(__file__).resolve().parents[2]
PAGE = Path(__file__).with_name("board.html")

_cache: tuple[tuple, dict] | None = None


def _stamp() -> tuple:
    """Changes whenever anything the board reads changes."""
    paths = [account.latest_capture(), board.CHALDEA, board.FARMS]
    return tuple(p.stat().st_mtime if p.exists() else 0 for p in paths)


async def board_data(request: Request) -> JSONResponse:
    global _cache
    try:
        stamp = _stamp()
    except FileNotFoundError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    if _cache is None or _cache[0] != stamp:
        _cache = (stamp, await asyncio.to_thread(board.board))
    return JSONResponse(_cache[1])


async def page(request: Request) -> HTMLResponse:
    return HTMLResponse(PAGE.read_text())


async def queue(request: Request) -> JSONResponse:
    if request.method == "POST":
        body = await request.json()
        try:
            task = tasks.add(body["kind"], body["title"], body.get("payload", {}), body.get("apples"))
        except (KeyError, ValueError) as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse(task)
    return JSONResponse(tasks.state())


async def queue_item(request: Request) -> JSONResponse:
    tasks.remove(request.path_params["id"])
    return JSONResponse(tasks.state())


async def queue_retry(request: Request) -> JSONResponse:
    tasks.retry(request.path_params["id"])
    return JSONResponse(tasks.state())


async def _service(unit: str, *command: str) -> str | None:
    proc = await asyncio.create_subprocess_exec(
        "systemd-run", "--user", f"--unit={unit}", "--collect", f"--working-directory={PROJECT}",
        f"--setenv=PATH={os.environ.get('PATH', '')}", f"--setenv=HOME={Path.home()}", *command,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    return None if proc.returncode == 0 else err.decode().strip()


def _busy() -> str | None:
    for unit, what in ((tasks.RUNNER_UNIT, "the queue is running"), (tasks.AGENT_UNIT, "an agent run is playing"),
                       (tasks.SYNC_UNIT, "a sync is running")):
        if tasks.unit_active(unit):
            return what
    return None


async def run_queue(request: Request) -> JSONResponse:
    if busy := _busy():
        return JSONResponse({"error": busy}, status_code=409)
    if error := await _service(tasks.RUNNER_UNIT, "uv", "run", "fgo-agent", "runner"):
        return JSONResponse({"error": error}, status_code=500)
    return JSONResponse(tasks.state())


async def stop_queue(request: Request) -> JSONResponse:
    await asyncio.create_subprocess_exec("systemctl", "--user", "stop", tasks.RUNNER_UNIT)
    await asyncio.sleep(1)
    for t in tasks.load():
        if t["status"] == "running":
            tasks.update(t["id"], status="stopped")
    return JSONResponse(tasks.state())


async def sync(request: Request) -> JSONResponse:
    if busy := _busy():
        return JSONResponse({"error": f"{busy}; it syncs by itself when it finishes"}, status_code=409)
    script = "scripts/emu.sh up && scripts/capture-account.sh; pgrep -x scrcpy > /dev/null || scripts/emu.sh down"
    if error := await _service(tasks.SYNC_UNIT, "bash", "-c", script):
        return JSONResponse({"error": error}, status_code=500)
    return JSONResponse(tasks.state())


LIVE_PAGE = Path(__file__).with_name("live.html")
SCREEN_W, SCREEN_H = 1280, 720
_device = None


def _input_device():
    global _device
    if _device is None:
        from .device import Device

        _device = Device()
    return _device


def _emulator_running() -> bool:
    out = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", "fgo-redroid"], capture_output=True, text=True)
    return out.stdout.strip() == "true"


async def live_page(request: Request) -> HTMLResponse:
    return HTMLResponse(LIVE_PAGE.read_text())


async def game(request: Request) -> JSONResponse:
    """GET: is the emulator up, and is an agent playing (then the page is view-only).
    POST {"action": "up" | "down"}: start the emulator with FGO, or close both."""
    if request.method == "POST":
        action = (await request.json()).get("action")
        if action not in ("up", "down"):
            return JSONResponse({"error": "action is up or down"}, status_code=400)
        if action == "down" and (busy := _busy()):
            return JSONResponse({"error": f"{busy}: it stops the emulator itself when it is done"}, status_code=409)
        proc = await asyncio.create_subprocess_exec("scripts/emu.sh", action, cwd=PROJECT,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
        if proc.returncode:
            return JSONResponse({"error": err.decode().strip().splitlines()[-1] if err else "emu.sh failed"}, status_code=500)
    running = await asyncio.to_thread(_emulator_running)
    return JSONResponse({"running": running, "busy": _busy()})


async def control(request: Request) -> JSONResponse:
    """Play by hand: {"type": "tap", "x", "y"} or {"type": "swipe", "x1", "y1", "x2", "y2", "ms"} with
    coordinates as fractions of the screen (0-1), or {"type": "back"}. Refused while an agent plays."""
    if busy := _busy():
        return JSONResponse({"error": f"{busy}: the game is view-only until it is done"}, status_code=409)
    body = await request.json()
    px = lambda v, size: max(0, min(size - 1, round(float(v) * size)))  # noqa: E731
    dev = _input_device()
    kind = body.get("type")
    if kind == "tap":
        await asyncio.to_thread(dev.tap, px(body["x"], SCREEN_W), px(body["y"], SCREEN_H))
    elif kind == "swipe":
        await asyncio.to_thread(dev.swipe, px(body["x1"], SCREEN_W), px(body["y1"], SCREEN_H),
                                px(body["x2"], SCREEN_W), px(body["y2"], SCREEN_H), int(body.get("ms", 300)))
    elif kind == "back":
        await asyncio.to_thread(dev.back)
    else:
        return JSONResponse({"error": "type is tap, swipe or back"}, status_code=400)
    return JSONResponse({"ok": True})


async def game_window(request: Request) -> JSONResponse:
    """Open the scrcpy game window (app/fgo.sh): no stream lag, for real-time play."""
    if busy := _busy():
        return JSONResponse({"error": f"{busy}: the window would be view-only; open it from the launcher to watch"}, status_code=409)
    subprocess.Popen([str(PROJECT / "app" / "fgo.sh")], cwd=PROJECT, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return JSONResponse({"ok": True})


routes = [
    Route("/board", page),
    Route("/live", live_page),
    Route("/api/game", game, methods=["GET", "POST"]),
    Route("/api/game/window", game_window, methods=["POST"]),
    Route("/api/control", control, methods=["POST"]),
    Route("/api/board", board_data),
    Route("/api/queue", queue, methods=["GET", "POST"]),
    Route("/api/queue/run", run_queue, methods=["POST"]),
    Route("/api/queue/stop", stop_queue, methods=["POST"]),
    Route("/api/queue/{id}", queue_item, methods=["DELETE"]),
    Route("/api/queue/{id}/retry", queue_retry, methods=["POST"]),
    Route("/api/sync", sync, methods=["POST"]),
]
