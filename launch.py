"""Start the local office and open its browser after the bound server is ready.

Python 3.10+; no installation step. The bundled room is the default. Override it
with --room-file, OFFICE_STUDIO_ROOM_FILE, or an owner-supplied private-room.html
beside this launcher. Explicit overrides stay outside the application assets.
"""
from __future__ import annotations

import argparse
import errno
import http.client
import os
from pathlib import Path
import re
import sys
import threading
import time
from urllib.parse import urlsplit
import webbrowser


ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True


def open_online():
    """Hand the configured hosted page to the browser, where sign-in takes place."""
    url = os.environ.get("OFFICE_STUDIO_ONLINE_URL")
    if not url:
        print("Ask your Office Studio administrator for the hosted site address. Set the "
              "OFFICE_STUDIO_ONLINE_URL user environment variable to that HTTPS address, "
              "then reopen Office Studio Online.", file=sys.stderr)
        return 1
    try:
        page = urlsplit(url)
        # Reject user info, ambiguous browser/URL-parser delimiters, and OAuth callback data.
        valid = (page.scheme == "https" and page.hostname and
                 re.fullmatch(r"(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:.]+\])(?::[0-9]{1,5})?", page.netloc) and
                 page.port != 0 and not any(c in url for c in '\\?#"<>') and
                 all(c.isprintable() and not c.isspace() for c in url))
    except ValueError:
        valid = False
    if not valid:
        print("Set OFFICE_STUDIO_ONLINE_URL to the hosted HTTPS page address without "
              "credentials, query parameters, or a fragment.", file=sys.stderr)
        return 1
    try:
        if webbrowser.open(url, new=2):
            return 0
    except KeyboardInterrupt:
        print("Online launch cancelled.", file=sys.stderr)
        return 1
    except (OSError, webbrowser.Error):
        pass
    print("Could not open the default browser. Open the configured hosted site address "
          "in your browser to sign in.", file=sys.stderr)
    return 1


def find_room(explicit=None):
    """Resolve one explicit override or the bundled room; never search folders."""
    room_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT
    chosen = explicit if explicit is not None else os.environ.get("OFFICE_STUDIO_ROOM_FILE")
    if chosen:
        candidate = Path(chosen).expanduser()
        if not candidate.is_absolute():
            candidate = room_root / candidate
        if not candidate.is_file():
            raise ValueError("The selected room file was not found. Check --room-file or OFFICE_STUDIO_ROOM_FILE.")
        return candidate.resolve()
    candidate = room_root / "private-room.html"
    return candidate.resolve() if candidate.is_file() else ROOT / "room" / "office.html"


def bind_office(factory, port, data_dir, room_file):
    """Bind our own server before considering a browser; never reuse a service."""
    try:
        return factory(port=port, data_dir=data_dir, room_file=room_file), False
    except OSError as error:
        # Windows can report an already-bound/excluded port as WSAEACCES.
        occupied = error.errno == errno.EADDRINUSE or getattr(error, "winerror", None) in (10013, 10048)
        if not occupied or port == 0:
            raise
    return factory(port=0, data_dir=data_dir, room_file=room_file), True


def open_when_ready(port, stopped, *, timeout=15):
    """Probe only our already-bound loopback socket; attempt browser open once."""
    url = f"http://127.0.0.1:{port}/"
    deadline = time.monotonic() + timeout
    while not stopped.is_set() and time.monotonic() < deadline:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        try:
            connection.request("GET", "/")
            ready = connection.getresponse().status == 200
        except (OSError, http.client.HTTPException):
            ready = False
        finally:
            connection.close()
        if ready and not stopped.is_set():
            try:
                opened = webbrowser.open(url, new=2)
            except Exception:
                opened = False
            if not opened:
                print(f"Open this address in your browser: {url}", flush=True)
            return
        stopped.wait(0.1)
    if not stopped.is_set():
        print(f"The page is not ready yet. Once ready, open: {url}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765, help="preferred loopback port; 0 chooses a free port")
    parser.add_argument("--data-dir", type=Path, help="local workspace storage (outside this app by default)")
    parser.add_argument("--room-file", type=Path, help="optional owner-supplied private HTML room; never copied into the app")
    parser.add_argument("--no-browser", action="store_true", help="serve without opening a browser")
    parser.add_argument("--configure", action="store_true", help="configure providers for this session before starting the office")
    parser.add_argument("--online", action="store_true", help="open the hosted site configured by OFFICE_STUDIO_ONLINE_URL")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        parser.error("Python 3.10 or newer is required.")
    if args.online:
        if args.no_browser or args.configure:
            parser.error("--online cannot be combined with --no-browser or --configure")
        return open_online()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    try:
        room_file = find_room(args.room_file)
    except ValueError as error:
        parser.error(str(error))
    try:
        if args.configure:
            from configure_providers import configure_session
            try:
                configure_session()
            except (EOFError, KeyboardInterrupt, ValueError):
                print("Provider setup cancelled. Office Studio was not started.", file=sys.stderr)
                return 1
        from server import create_server
        data_dir = args.data_dir or Path.home() / ".office-studio"
        office, fallback = bind_office(create_server, args.port, data_dir, room_file)
    except ImportError:
        print("Office Studio could not load its server. Extract the complete app folder and try again.", file=sys.stderr)
        return 1
    except Exception:
        print("Office Studio could not start. Check that the storage folder is writable and local ports are available.", file=sys.stderr)
        return 1
    port = office.server_port
    if fallback:
        print(f"Port {args.port} is unavailable; using a free port for this Office Studio session.", flush=True)
    print(f"Office Studio: http://127.0.0.1:{port}/", flush=True)
    print("Offices stay on this computer. Keep this window open; press Ctrl+C to stop.", flush=True)
    print("Office Suite room enabled.", flush=True)
    stopped = threading.Event()
    browser = None
    if not args.no_browser:
        browser = threading.Thread(target=open_when_ready, args=(port, stopped), daemon=True)
        browser.start()
    try:
        office.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        office.server_close()
        if browser:
            browser.join(timeout=1.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
