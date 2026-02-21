#!/usr/bin/env python
"""Standalone dev server for the prism web viewer."""
import http.server
import functools
import shutil
import os
import signal
from pathlib import Path

def main():
    os.chdir(Path(__file__).parent)
    web_dir = Path("web").resolve()

    # Copy callgraph data
    src = Path(".callgraph")
    dst = web_dir / ".callgraph"
    if src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_dir), **kwargs)

        def do_GET(self):
            if self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            super().do_GET()

        def end_headers(self):
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            super().end_headers()

        def log_message(self, format, *args):
            pass  # suppress logs

    httpd = http.server.ThreadingHTTPServer(("", 8080), Handler)
    print("Serving at http://localhost:8080", flush=True)
    httpd.serve_forever()

if __name__ == "__main__":
    main()
