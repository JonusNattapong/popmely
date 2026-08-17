"""Local web dashboard for the popmely SQLite database.

Serves a single-page dashboard over the trading database on localhost. Built on
the standard library only (no Flask/FastAPI) so it adds no dependency to the
package, and it holds no MT5 connection - it only reads ~/.popmely/popmely.db.

Usage:
    python -m popmely.dashboard --port 8787
    popmely-dashboard --port 8787 --no-browser
"""

import json
import logging
import argparse
import mimetypes
import threading
import webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from popmely.dashboard import queries

logger = logging.getLogger("popmely.dashboard")

STATIC_DIR = Path(__file__).parent / "static"


class DashboardHandler(BaseHTTPRequestHandler):
    """Routes: / -> the page, /api/data -> JSON payload, /static/<file> -> assets."""

    server_version = "popmely-dashboard/5.0.0"
    db_path = queries.DB_PATH

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            self._send_static("index.html")
        elif path == "/api/data":
            self._send_json(queries.collect(self.db_path))
        elif path == "/api/health":
            self._send_json({"status": "ok", "database": str(self.db_path)})
        elif path == "/api/goal":
            chal_path = Path.home() / ".popmely" / "challenge.json"
            if chal_path.exists():
                with open(chal_path, "r") as f:
                    self._send_json(json.load(f))
            else:
                self._send_json({"running": False})
        elif path.startswith("/static/"):
            self._send_static(path[len("/static/"):])
        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self._send_error(404, "Not found")

    # -- responses ---------------------------------------------------------

    def _send_json(self, payload: dict):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, name: str):
        # Resolve under STATIC_DIR and reject anything that escapes it.
        target = (STATIC_DIR / name).resolve()
        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._send_error(403, "Forbidden")
            return

        if not target.is_file():
            self._send_error(404, "Not found")
            return

        body = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str):
        body = json.dumps({"status": "error", "message": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args):
        logger.debug("%s - %s", self.address_string(), format % args)


def serve(
    host: str = "127.0.0.1",
    port: int = 8787,
    db_path: Path = queries.DB_PATH,
    open_browser: bool = True,
):
    """Start the dashboard server and block until interrupted."""
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"db_path": db_path})
    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"

    print("=" * 70)
    print(" popmely Data Dashboard v5.0.0")
    print(f" Serving  : {url}")
    print(f" Database : {db_path}")
    if not db_path.exists():
        print(" Notice   : database not found yet - the page will show an empty state.")
    print(" Press Ctrl+C to stop.")
    print("=" * 70)

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description="popmely local data dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="Port (default: 8787)")
    parser.add_argument("--db", default=str(queries.DB_PATH), help="Path to popmely.db")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser window")
    parser.add_argument("--verbose", action="store_true", help="Log every request")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    serve(
        host=args.host,
        port=args.port,
        db_path=Path(args.db).expanduser(),
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
