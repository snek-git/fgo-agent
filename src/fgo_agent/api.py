"""HTTP API behind the board: account to-do data, the task queue, and account sync.

The web board (/board) and the desktop app both use these routes, so they always agree.
Long jobs (the queue runner, a sync) run as user services so they outlive the request, the
page, and the server itself.
"""

import asyncio
import os
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


routes = [
    Route("/board", page),
    Route("/api/board", board_data),
    Route("/api/queue", queue, methods=["GET", "POST"]),
    Route("/api/queue/run", run_queue, methods=["POST"]),
    Route("/api/queue/stop", stop_queue, methods=["POST"]),
    Route("/api/queue/{id}", queue_item, methods=["DELETE"]),
    Route("/api/sync", sync, methods=["POST"]),
]
