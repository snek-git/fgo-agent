"""mitmproxy addon: save FGO's login response (the whole account: servants, CEs, items).

Only response bodies of the login call are written, never requests, which carry the account's
signed auth parameters. Every FGO request path is printed so a failed capture is easy to read.
"""

import time
from pathlib import Path

from mitmproxy import http

OUT = Path(__file__).resolve().parents[1] / "data" / "capture"


def response(flow: http.HTTPFlow) -> None:
    host = flow.request.pretty_host
    if "fate-go" not in host:
        return
    print(f"fgo {flow.request.method} {host}{flow.request.path.split('?')[0]} -> {flow.response.status_code}")
    if "/login/top" in flow.request.path:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"login-top-{time.strftime('%Y%m%d-%H%M%S')}.json"
        path.write_bytes(flow.response.content or b"")
        print(f"saved login response ({len(flow.response.content or b'')} bytes) to {path}")
