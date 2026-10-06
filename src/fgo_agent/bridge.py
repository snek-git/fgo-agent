"""Client for the Kotlin bridge (bridge/), which runs FGA's own battle modules over adb."""

import json
import subprocess
import threading
from pathlib import Path

BINARY = Path(__file__).resolve().parents[2] / "bridge" / "build" / "install" / "fga-bridge" / "bin" / "fga-bridge"


class BridgeError(RuntimeError):
    pass


class Bridge:
    def __init__(self) -> None:
        if not BINARY.exists():
            raise BridgeError(f"bridge not built: run scripts/build-bridge.sh ({BINARY} missing)")
        self._proc = subprocess.Popen(
            [str(BINARY)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, text=True, bufsize=1
        )
        self._lock = threading.Lock()
        self._read()  # {"ready": true}

    def _read(self) -> dict:
        line = self._proc.stdout.readline()
        if not line:
            raise BridgeError(f"bridge exited with code {self._proc.poll()}")
        return json.loads(line)

    def call(self, cmd: str, **args) -> dict:
        with self._lock:
            self._proc.stdin.write(json.dumps({"cmd": cmd, **args}) + "\n")
            self._proc.stdin.flush()
            reply = self._read()
        if not reply.pop("ok"):
            raise BridgeError(reply["error"])
        return reply

    def close(self) -> None:
        if self._proc.poll() is None:
            self.call("quit")
            self._proc.wait(timeout=10)
