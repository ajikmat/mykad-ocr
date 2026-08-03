#!/usr/bin/env python3
"""Demo server: serves the repo statically AND plays the Scan Proxy role,
forwarding POST /api/scan-mykad to the OCR Service — the same architecture
the Laravel proxy implements in production (SPEC.md §6).

Usage:  python3 examples/demo/serve.py [--port 5173] [--ocr http://127.0.0.1:8000]
Then open http://localhost:5173/examples/demo/
"""

import argparse
import http.server
import urllib.error
import urllib.request
from functools import partial
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class Handler(http.server.SimpleHTTPRequestHandler):
    ocr_url = "http://127.0.0.1:8000"

    def do_POST(self):
        if self.path != "/api/scan-mykad":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        req = urllib.request.Request(
            self.ocr_url.rstrip("/") + "/scan",
            data=body,
            headers={"Content-Type": self.headers.get("Content-Type", "")},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                payload, status = res.read(), res.status
        except urllib.error.HTTPError as e:
            payload, status = e.read(), e.code
        except OSError:
            payload, status = b'{"ok":false,"reason":"SERVICE_DOWN"}', 502
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5173)
    ap.add_argument("--ocr", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    Handler.ocr_url = args.ocr
    handler = partial(Handler, directory=str(REPO_ROOT))
    print(f"demo:  http://localhost:{args.port}/examples/demo/")
    print(f"proxy: /api/scan-mykad -> {args.ocr}/scan")
    http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()


if __name__ == "__main__":
    main()
