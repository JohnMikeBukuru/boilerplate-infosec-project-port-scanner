#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_JSON_PATH = os.path.join(PROJECT_DIR, "result.json")

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")


def serve_static(handler, path):
    # map URL to file inside /src
    if path == "/":
        file_path = os.path.join(SRC_DIR, "index.html")
    else:
        # remove leading /
        rel = path.lstrip("/")
        file_path = os.path.join(SRC_DIR, rel)

    if not os.path.isfile(file_path):
        handler.send_response(404)
        handler.send_header("Content-Type", "text/plain")
        handler.end_headers()
        handler.wfile.write(b"Not found")
        return

    ctype, _ = mimetypes.guess_type(file_path)
    if not ctype:
        ctype = "application/octet-stream"

    with open(file_path, "rb") as f:
        content = f.read()

    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    # CORS (so your JS client can fetch /result)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        # Preflight for CORS
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        # API route (your existing logic)
        if path == "/result":
            if not os.path.exists(RESULT_JSON_PATH):
                return _send_json(
                    self,
                    200,
                    {
                        "ok": False,
                        "message": "You must start typing your solution in port_scanner.py and run: python main.py",
                    },
                )

            with open(RESULT_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            return _send_json(self, 200, data)

        if path == "/user-email":
            email = ""
            try:
                email = subprocess.check_output(
                    ["git", "config", "--get", "user.email"],
                    stderr=subprocess.DEVNULL,
                ).decode("utf-8").strip()
            except Exception:
                email = ""
        
            return _send_json(self, 200, {"email": email})

        if (
            path == "/"
            or path.endswith(".css")
            or path.endswith(".js")
            or path.endswith(".png")
            or path.endswith(".jpg")
            or path.endswith(".jpeg")
            or path.endswith(".svg")
            or path.endswith(".webp")
        ):
            return serve_static(self, path)

        # fallback 404
        return _send_json(
            self,
            200,
            {
                "ok": False,
                "state": "missing",  # 2nd key ✅
                "message": "You must start typing your solution in port_scanner.py and run: python main.py",
            },
        )
def main():
    port = int(os.environ.get("PORT", "3000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Server listening on http://0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
