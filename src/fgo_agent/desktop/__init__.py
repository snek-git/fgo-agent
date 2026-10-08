"""Desktop app for the board: the same data and orders as the web page, in a native Qt window.

A thin client over the board API (fgo_agent.api) served by `fgo-agent view`; it starts that
server as a user service when nothing answers on the port, and leaves it running for the web
board and the live viewer.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
PORT = 8765


def _api_up(base: str) -> bool | None:
    """True if the board API answers, False if an old viewer without it does, None if nothing."""
    try:
        with urllib.request.urlopen(f"{base}/api/queue", timeout=2) as r:
            json.load(r)
        return True
    except urllib.error.HTTPError:
        return False
    except (urllib.error.URLError, OSError, ValueError):
        return None


def ensure_server(port: int) -> str | None:
    """Make sure the board API is up; returns an error message for the window otherwise."""
    base = f"http://127.0.0.1:{port}"
    state = _api_up(base)
    if state:
        return None
    if state is False:
        return (f"An older `fgo-agent view` is running on port {port} without the board API. "
                "Restart it (Ctrl+C, then `uv run fgo-agent view`) and reopen this app.")
    subprocess.run(["systemd-run", "--user", "--unit=fgo-agent-view", "--collect", f"--working-directory={PROJECT}",
                    f"--setenv=PATH={os.environ.get('PATH', '')}", f"--setenv=HOME={Path.home()}",
                    "uv", "run", "fgo-agent", "view", "--port", str(port)], capture_output=True)
    for _ in range(40):
        if _api_up(base):
            return None
        time.sleep(0.5)
    return "Could not start the board server: see `journalctl --user -u fgo-agent-view`."


def main(port: int = PORT) -> None:
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Chaldea Terminal")
    app.setDesktopFileName("chaldea-terminal")
    icon = PROJECT / "app" / "fgo.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"apiBase": f"http://127.0.0.1:{port}", "startupError": ensure_server(port) or ""})
    engine.load(str(Path(__file__).with_name("Main.qml")))
    if not engine.rootObjects():
        sys.exit(1)
    sys.exit(app.exec())
