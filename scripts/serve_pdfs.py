#!/usr/bin/env python3
"""Serve reports/ with forced PDF download (avoids black Chrome PDF viewer)."""
from __future__ import annotations

import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1] / "reports"
PORT = 43145


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        path = unquote(urlparse(self.path).path)
        lower = path.lower()
        if lower.endswith((".pdf", ".pptx")):
            name = Path(path).name
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def guess_type(self, path):
        lower = str(path).lower()
        if lower.endswith(".pdf"):
            return "application/pdf"
        if lower.endswith(".pptx"):
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        return super().guess_type(path)


if __name__ == "__main__":
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Serving {ROOT} on http://127.0.0.1:{PORT}/ (PDFs as attachment)")
    httpd.serve_forever()
