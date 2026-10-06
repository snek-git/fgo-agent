"""fgo-agent: harness for an AI agent to play Fate/Grand Order on redroid."""

import argparse
import json
import time


def main() -> None:
    parser = argparse.ArgumentParser(prog="fgo-agent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="run the MCP server on stdio")
    sub.add_parser("observe", help="print the parsed screen state")
    shot = sub.add_parser("shot", help="save a screenshot")
    shot.add_argument("path", nargs="?", default="screen.png")
    sub.add_parser("bench", help="time screenshot + parse")
    args = parser.parse_args()

    if args.cmd == "serve":
        from .server import run

        run()
        return

    import cv2

    from .game import Game

    game = Game()
    if args.cmd == "observe":
        state, _ = game.observe()
        print(json.dumps(state, indent=2))
    elif args.cmd == "shot":
        image, _ = game.capture()
        cv2.imwrite(args.path, image)
        print(args.path, image.shape)
    elif args.cmd == "bench":
        for _ in range(5):
            start = time.perf_counter()
            state, _ = game.observe()
            print(f"{(time.perf_counter() - start) * 1000:.0f} ms  {state['screen']}")
