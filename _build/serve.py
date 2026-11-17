#!/usr/bin/env python3
"""Serve _site/ on a port and rebuild on source file change.

Watches all .md / .yml / .html / .css / .py under src/ (skipping _site/ and
__pycache__/). On any change, runs build.py. Unknown paths get /404.html,
like GitHub Pages.

Usage: python3 _build/serve.py [port]   (default 8765)
"""
import functools
import http.server
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
BUILD = SRC / "_build" / "build.py"
SITE = SRC / "_site"
SUFFIXES = {".md", ".yml", ".yaml", ".html", ".css", ".py", ".js"}
SKIP_DIRS = {"_site", "__pycache__", ".git"}


def collect_mtimes() -> dict[Path, float]:
    out: dict[Path, float] = {}
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if Path(name).suffix.lower() in SUFFIXES:
                p = Path(root) / name
                try:
                    out[p] = p.stat().st_mtime
                except OSError:
                    pass
    return out


def build() -> None:
    subprocess.run([sys.executable, str(BUILD)], cwd=SRC, check=False)


def pick_port(preferred: int, tries: int = 20) -> int:
    """Return `preferred` if free, else the next open port. Warn on fallback."""
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("", port))
                if port != preferred:
                    print(
                        f"⚠ port {preferred} is in use — using {port} instead",
                        flush=True,
                    )
                    print(
                        f"  (to free {preferred}:  lsof -ti :{preferred} | xargs kill)",
                        flush=True,
                    )
                return port
            except OSError:
                continue
    sys.exit(
        f"✗ no free port in {preferred}–{preferred + tries - 1}; "
        f"free one with:  lsof -ti :{preferred} | xargs kill"
    )


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a) -> None:
        pass

    def send_error(self, code: int, *a, **k) -> None:
        page = SITE / "404.html"
        if code == 404 and page.exists():
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.read_bytes())
            return
        super().send_error(code, *a, **k)


def main() -> None:
    requested = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    port = pick_port(requested)

    print("→ initial build…", flush=True)
    build()

    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(
        ("", port), functools.partial(Handler, directory=str(SITE))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"→ serving http://localhost:{port}/   (Ctrl-C to stop)", flush=True)

    last = collect_mtimes()
    print(f"→ watching {len(last)} files", flush=True)
    try:
        while True:
            time.sleep(1)
            curr = collect_mtimes()
            changed = sorted(
                {p for p in curr if last.get(p) != curr.get(p)}
                | {p for p in last if p not in curr}
            )
            if changed:
                for p in changed[:5]:
                    rel = p.relative_to(SRC) if p.exists() else p.name
                    print(f"  · {rel}", flush=True)
                if len(changed) > 5:
                    print(f"  · (+{len(changed) - 5} more)", flush=True)
                build()
                last = collect_mtimes()
    except KeyboardInterrupt:
        print("\n→ stopping…", flush=True)
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
