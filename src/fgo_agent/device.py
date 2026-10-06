"""Talks to the Android container over adb. All coordinates are screen pixels (1280x720)."""

import subprocess

import cv2
import numpy as np

SERIAL = "127.0.0.1:5555"
FGO_PACKAGE = "com.aniplex.fategrandorder"


class Device:
    def __init__(self, serial: str = SERIAL):
        self.serial = serial
        subprocess.run(["adb", "connect", serial], capture_output=True, timeout=10)

    def adb(self, *args: str, timeout: float = 20) -> bytes:
        result = subprocess.run(
            ["adb", "-s", self.serial, *args], capture_output=True, timeout=timeout
        )
        if result.returncode != 0:
            raise RuntimeError(f"adb {' '.join(args)} failed: {result.stderr.decode()}")
        return result.stdout

    def shell(self, command: str) -> str:
        return self.adb("shell", command).decode()

    def screenshot(self) -> np.ndarray:
        """Raw framebuffer grab (no PNG encode on the device). Returns a BGR image."""
        raw = self.adb("exec-out", "screencap")
        width, height = np.frombuffer(raw[:8], dtype=np.uint32)
        header = len(raw) - int(width) * int(height) * 4
        rgba = np.frombuffer(raw[header:], dtype=np.uint8).reshape(int(height), int(width), 4)
        return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)

    def tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {int(x)} {int(y)}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> None:
        self.shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(ms)}")

    def back(self) -> None:
        self.shell("input keyevent KEYCODE_BACK")

    def launch_fgo(self) -> None:
        self.shell(f"monkey -p {FGO_PACKAGE} -c android.intent.category.LAUNCHER 1")

    def fgo_running(self) -> bool:
        return bool(self.shell(f"pidof {FGO_PACKAGE} || true").strip())
