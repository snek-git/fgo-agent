"""Live video and audio from the emulator for the viewer page.

Video: Android's screenrecord (H.264) decoded by ffmpeg into JPEG frames at up to 30 fps.
screenrecord stops after 3 minutes, so it is restarted in a loop; if it fails, plain
screenshots keep the page alive.

Audio: the scrcpy server (shipped with scrcpy, version-locked to it) captures the device output
as raw PCM over an adb-forwarded socket; ffmpeg turns that into a live MP3 stream.

Each source runs only while someone is watching or listening.
"""

import queue
import random
import re
import socket
import subprocess
import threading
import time

from .device import SERIAL, Device, encode_jpeg

ADB = ["adb", "-s", SERIAL]
FPS = 30
SCRCPY_SERVER = "/usr/share/scrcpy/scrcpy-server"


class Source:
    """A background producer that runs while it has users."""

    def __init__(self) -> None:
        self.users = 0
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None

    def join(self) -> None:
        with self.lock:
            self.users += 1
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, daemon=True)
                self.thread.start()

    def leave(self) -> None:
        with self.lock:
            self.users -= 1

    def _run(self) -> None:
        try:
            self.produce()
        finally:
            with self.lock:
                self.thread = None

    def produce(self) -> None:
        raise NotImplementedError


class Video(Source):
    def __init__(self) -> None:
        super().__init__()
        self.frame: bytes | None = None
        self.seq = 0

    def _publish(self, frame: bytes) -> None:
        self.frame = frame
        self.seq += 1

    def produce(self) -> None:
        while self.users > 0:
            started = time.monotonic()
            self._screenrecord()
            if time.monotonic() - started < 5:  # recorder broken, not just its 3 minute limit
                self._screenshots(seconds=30)

    def _screenrecord(self) -> None:
        record = subprocess.Popen(
            ADB + ["exec-out", "screenrecord", "--output-format=h264", "--size", "1280x720",
                   "--bit-rate", "8000000", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        decode = subprocess.Popen(
            # a tiny probesize never finds the stream headers; screenrecord's limited-range color
            # needs -strict unofficial for the JPEG encoder
            ["ffmpeg", "-v", "error", "-probesize", "200000", "-f", "h264", "-i", "pipe:0",
             "-vf", f"fps={FPS}", "-strict", "unofficial", "-q:v", "5",
             "-f", "image2pipe", "-c:v", "mjpeg", "pipe:1"],
            stdin=record.stdout, stdout=subprocess.PIPE)
        record.stdout.close()  # ffmpeg owns it now
        buffer = b""
        try:
            while self.users > 0:
                chunk = decode.stdout.read1(1 << 16)
                if not chunk:
                    return
                buffer += chunk
                # JPEG frames end with FFD9; inside entropy-coded data FF is always stuffed
                while (end := buffer.find(b"\xff\xd9")) != -1:
                    start = buffer.find(b"\xff\xd8")
                    if 0 <= start < end:
                        self._publish(buffer[start:end + 2])
                    buffer = buffer[end + 2:]
        finally:
            for process in (decode, record):
                process.kill()
                process.wait()

    def _screenshots(self, seconds: float) -> None:
        device = Device()
        until = time.monotonic() + seconds
        while self.users > 0 and time.monotonic() < until:
            try:
                self._publish(encode_jpeg(device.screenshot(), quality=70))
            except Exception:
                time.sleep(1)
            time.sleep(0.2)


class Audio(Source):
    def __init__(self) -> None:
        super().__init__()
        self.listeners: set[queue.Queue] = set()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=64)
        with self.lock:
            self.listeners.add(q)
        self.join()
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            self.listeners.discard(q)
        self.leave()

    def produce(self) -> None:
        while self.users > 0:
            try:
                self._stream()
            except Exception:
                time.sleep(2)  # server died or device restarting; retry while someone listens

    def _stream(self) -> None:
        version = re.search(r"scrcpy (\S+)", subprocess.run(["scrcpy", "--version"], capture_output=True,
                                                            text=True).stdout).group(1)
        scid = f"{random.randrange(1, 0x7FFFFFFF):08x}"
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        subprocess.run(ADB + ["push", SCRCPY_SERVER, "/data/local/tmp/scrcpy-server.jar"],
                       check=True, capture_output=True)
        subprocess.run(ADB + ["forward", f"tcp:{port}", f"localabstract:scrcpy_{scid}"],
                       check=True, capture_output=True)
        server = subprocess.Popen(
            ADB + ["shell", "CLASSPATH=/data/local/tmp/scrcpy-server.jar", "app_process", "/",
                   "com.genymobile.scrcpy.Server", version, f"scid={scid}", "log_level=warn",
                   "video=false", "control=false", "audio=true", "audio_codec=raw",
                   "audio_source=output", "tunnel_forward=true", "raw_stream=true"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        encode = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "pipe:0",
             "-c:a", "libmp3lame", "-b:a", "160k", "-f", "mp3", "-flush_packets", "1", "pipe:1"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        pcm = None
        try:
            # adb accepts a forward before the server listens and then closes it: retry until data
            for _ in range(100):
                pcm = socket.create_connection(("127.0.0.1", port), timeout=5)
                first = pcm.recv(1 << 16)
                if first:
                    encode.stdin.write(first)
                    break
                pcm.close()
                pcm = None
                time.sleep(0.1)
            if pcm is None:
                raise RuntimeError("scrcpy audio server did not start")
            pump = threading.Thread(target=self._pump, args=(pcm, encode), daemon=True)
            pump.start()
            while self.users > 0:
                chunk = encode.stdout.read1(1 << 14)
                if not chunk:
                    return
                with self.lock:
                    listeners = list(self.listeners)
                for q in listeners:
                    try:
                        q.put_nowait(chunk)
                    except queue.Full:  # a stalled listener drops audio, it never blocks the rest
                        pass
        finally:
            if pcm:
                pcm.close()
            for process in (encode, server):
                process.kill()
                process.wait()
            subprocess.run(ADB + ["forward", "--remove", f"tcp:{port}"], capture_output=True)

    def _pump(self, pcm: socket.socket, encode: subprocess.Popen) -> None:
        try:
            while self.users > 0:
                data = pcm.recv(1 << 16)
                if not data:
                    break
                encode.stdin.write(data)
        except (OSError, ValueError):
            pass
        finally:
            try:
                encode.stdin.close()
            except OSError:
                pass
