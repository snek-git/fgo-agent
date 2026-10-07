"""fgo-agent: harness for an AI agent to play Fate/Grand Order on redroid."""

import argparse
import json
import time


def main() -> None:
    parser = argparse.ArgumentParser(prog="fgo-agent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="run the MCP server on stdio")
    sub.add_parser("screen", help="print FGA's reading of the current screen")
    shot = sub.add_parser("shot", help="save a screenshot")
    shot.add_argument("path", nargs="?", default="screen.png")
    sub.add_parser("bench", help="time FGA's screen detection through the bridge")
    watch = sub.add_parser("watch", help="follow a headless play log live (latest by default)")
    watch.add_argument("log", nargs="?")
    view = sub.add_parser("view", help="web page: live game screen with the agent's feed under it")
    view.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to open it from your phone on the LAN")
    view.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.cmd == "view":
        from .view import run as view_run

        view_run(args.host, args.port)
        return

    if args.cmd == "watch":
        from .watch import main as watch_main

        watch_main([args.log] if args.log else [])
        return

    if args.cmd == "serve":
        from .server import run

        run()
        return

    if args.cmd == "shot":
        import cv2

        from .device import Device

        image = Device().screenshot()
        cv2.imwrite(args.path, image)
        print(args.path, image.shape)
        return

    from .bridge import Bridge

    bridge = Bridge()
    try:
        if args.cmd == "screen":
            print(json.dumps(bridge.call("screen"), indent=2))
        elif args.cmd == "bench":
            for _ in range(5):
                start = time.perf_counter()
                screen = bridge.call("screen")["screen"]
                print(f"{(time.perf_counter() - start) * 1000:.0f} ms  {screen}")
    finally:
        bridge.close()
