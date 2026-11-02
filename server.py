"""Private, loopback-only Office Studio. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import base64
import binascii
import importlib
import json
import re
import sqlite3
import struct
import uuid
import zlib
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

from loopback_server import LoopbackHTTPServer

ROOT = Path(__file__).resolve().parent
MAX_BODY = 1_048_576
MAX_LOGO_BYTES = 512_000
MAX_WORKSPACES = 200
MAX_DRAFTS = 100
ID = r"[0-9a-f]{32}"


class APIError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def text(value, field, limit, *, required=False, label=False):
    if not isinstance(value, str):
        raise APIError(f"{field} must be text.")
    value = value.strip()
    if len(value) > limit or (required and not value):
        raise APIError(f"{field} must contain {'1 to ' if required else 'at most '}{limit} characters.")
    if any(ord(c) < 32 and c not in ("\n", "\t") for c in value):
        raise APIError(f"{field} contains unsupported characters.")
    if label and any(c in value for c in "\n\r\t"):
        raise APIError(f"{field} must be a single line.")
    return value


def fields(data, allowed):
    if not isinstance(data, dict) or set(data) - set(allowed):
        raise APIError("Unexpected request fields.")


def string_list(value, field, count=20, length=100):
    if not isinstance(value, list) or len(value) > count:
        raise APIError(f"{field} must be a list of at most {count} items.")
    return [text(v, field, length, required=True, label=True) for v in value]


def dimensions_ok(width, height):
    if not (1 <= width <= 4096 and 1 <= height <= 4096 and width * height <= 4_194_304):
        raise APIError("Logo dimensions must be at most 4096 per side and 4 megapixels.")


def check_png(raw):
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError()
    pos, first, image = 8, True, False
    compressed = bytearray()
    while pos + 12 <= len(raw):
        size = int.from_bytes(raw[pos:pos + 4], "big")
        kind = raw[pos + 4:pos + 8]
        end = pos + 12 + size
        if end > len(raw) or not re.fullmatch(b"[A-Za-z]{4}", kind):
            raise ValueError()
        body = raw[pos + 8:pos + 8 + size]
        crc = int.from_bytes(raw[pos + 8 + size:end], "big")
        if zlib.crc32(kind + body) & 0xffffffff != crc:
            raise ValueError()
        if first:
            if kind != b"IHDR" or size != 13:
                raise ValueError()
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
            dimensions_ok(width, height)
            depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
            if depth not in depths.get(color, ()) or compression or filtering or interlace not in (0, 1):
                raise ValueError()
            first = False
        elif kind == b"IHDR" or kind in (b"acTL", b"fcTL", b"fdAT"):
            raise ValueError()
        if kind == b"IDAT":
            image = True
            compressed.extend(body)
        if kind == b"IEND":
            if size or end != len(raw) or not image:
                raise ValueError()
            # Each scanline starts with one filter byte. Adam7 stores seven
            # smaller images; empty passes contribute no rows or filter bytes.
            bits = depth * {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
            passes = ((0, 0, 1, 1),) if not interlace else (
                (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8),
                (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))
            rows = []
            for x, y, dx, dy in passes:
                across = max(0, (width - x + dx - 1) // dx)
                down = max(0, (height - y + dy - 1) // dy)
                if across and down:
                    rows.append((down, 1 + (across * bits + 7) // 8))
            expected = sum(count * stride for count, stride in rows)
            decoder = zlib.decompressobj()
            try:
                pixels = decoder.decompress(compressed, expected + 1)
            except zlib.error:
                raise ValueError() from None
            # Never flush without a bound. The extra byte detects inflation
            # beyond the exact dimension-derived budget, including tiny bombs.
            if len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise ValueError()
            offset = 0
            for count, stride in rows:
                for _ in range(count):
                    if pixels[offset] > 4:
                        raise ValueError()
                    offset += stride
            return
        pos = end
    raise ValueError()


def check_jpeg(raw):
    if not raw.startswith(b"\xff\xd8") or not raw.endswith(b"\xff\xd9"):
        raise ValueError()
    pos, dimensions, scan = 2, False, False
    while pos < len(raw):
        if raw[pos] != 255:
            raise ValueError()
        while pos < len(raw) and raw[pos] == 255:
            pos += 1
        if pos >= len(raw):
            raise ValueError()
        marker = raw[pos]
        pos += 1
        if marker == 0xd9:
            if pos == len(raw) and dimensions and scan:
                return
            raise ValueError()
        if marker in (0, 0xd8) or 0xd0 <= marker <= 0xd7:
            raise ValueError()
        if pos + 2 > len(raw):
            raise ValueError()
        size = int.from_bytes(raw[pos:pos + 2], "big")
        if size < 2 or pos + size > len(raw):
            raise ValueError()
        if marker in (0xc0, 0xc1, 0xc2):
            if size < 8:
                raise ValueError()
            dimensions_ok(int.from_bytes(raw[pos + 5:pos + 7], "big"), int.from_bytes(raw[pos + 3:pos + 5], "big"))
            dimensions = True
        pos += size
        if marker == 0xda:
            scan = True
            # Entropy bytes use FF00 escaping and restart markers; find the next segment.
            while pos < len(raw):
                if raw[pos] != 255:
                    pos += 1
                    continue
                start = pos
                while pos < len(raw) and raw[pos] == 255:
                    pos += 1
                if pos >= len(raw):
                    raise ValueError()
                if raw[pos] == 0 or 0xd0 <= raw[pos] <= 0xd7:
                    pos += 1
                    continue
                pos = start
                break
    raise ValueError()


def check_webp(raw):
    if len(raw) < 20 or raw[:4] != b"RIFF" or raw[8:12] != b"WEBP" or int.from_bytes(raw[4:8], "little") + 8 != len(raw):
        raise ValueError()
    pos, image = 12, False
    while pos + 8 <= len(raw):
        kind, size = raw[pos:pos + 4], int.from_bytes(raw[pos + 4:pos + 8], "little")
        body = raw[pos + 8:pos + 8 + size]
        end = pos + 8 + size + (size & 1)
        if end > len(raw):
            raise ValueError()
        if kind in (b"ANIM", b"ANMF"):
            raise ValueError()
        if kind == b"VP8X":
            if len(body) != 10 or body[0] & 2:
                raise ValueError()
            dimensions_ok(1 + int.from_bytes(body[4:7], "little"), 1 + int.from_bytes(body[7:10], "little"))
        elif kind == b"VP8 ":
            if len(body) < 10 or body[3:6] != b"\x9d\x01\x2a":
                raise ValueError()
            dimensions_ok(int.from_bytes(body[6:8], "little") & 0x3fff, int.from_bytes(body[8:10], "little") & 0x3fff)
            image = True
        elif kind == b"VP8L":
            if len(body) < 5 or body[0] != 47:
                raise ValueError()
            bits = int.from_bytes(body[1:5], "little")
            dimensions_ok((bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1)
            image = True
        pos = end
    if pos != len(raw) or not image:
        raise ValueError()


def logo(value):
    if not isinstance(value, str):
        raise APIError("logo must be text.")
    if not value:
        return ""
    if len(value) > 700_000:
        raise APIError("Logo is too large.")
    match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/]*={0,2})", value)
    if not match:
        raise APIError("Logo must be a PNG, JPEG or WebP data image.")
    try:
        raw = base64.b64decode(match[2], validate=True)
        if not raw or len(raw) > MAX_LOGO_BYTES:
            raise ValueError()
        {"png": check_png, "jpeg": check_jpeg, "webp": check_webp}[match[1]](raw)
    except (ValueError, binascii.Error, struct.error):
        raise APIError("Logo is not a supported image or exceeds 512 KB.") from None
    return value


def agent(data, *, intake=False):
    allowed = {"name", "specialty", "instruction"}
    if intake:
        allowed |= {"engine", "color", "style", "systems"}
    fields(data, allowed)
    result = {key: text(data.get(key, ""), key, limit, required=True, label=key != "instruction")
              for key, limit in (("name", 60), ("specialty", 120), ("instruction", 4000))}
    result["routing"] = {"provider": "demo", "model": ""}
    if intake:
        for key, limit in (("engine", 100), ("color", 40), ("style", 60)):
            if key in data:
                result[key] = text(data[key], key, limit, label=True)
        if "systems" in data:
            result["systems"] = string_list(data["systems"], "systems")
    return result


def workspace(data):
    fields(data, {"name", "town", "color", "logo", "practice", "crew", "gates", "rules"})
    result = {"id": uuid.uuid4().hex, "name": text(data.get("name", ""), "name", 120, required=True, label=True),
              "town": text(data.get("town", ""), "town", 100, label=True),
              "practice": text(data.get("practice", "General business"), "practice", 100, required=True, label=True),
              "logo": logo(data.get("logo", "")), "color": data.get("color", "#a70008"),
              "rules": text(data.get("rules", ""), "rules", 8000), "manualUrl": "", "drafts": []}
    if not isinstance(result["color"], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", result["color"]):
        raise APIError("color must be a six-digit hex color.")
    crew = data.get("crew", [])
    if not isinstance(crew, list) or len(crew) > 10:
        raise APIError("crew must contain at most ten agents.")
    result["crew"] = [agent(item, intake=True) for item in crew]
    names = [item["name"].casefold() for item in result["crew"]]
    if len(set(names)) != len(names):
        raise APIError("Agent names must be unique.")
    gates = data.get("gates", [])
    if not isinstance(gates, list) or len(gates) > 40:
        raise APIError("gates must contain at most forty items.")
    result["gates"] = []
    exact_names = {item["name"] for item in result["crew"]}
    for item in gates:
        fields(item, {"owner", "need", "brief"})
        owner = text(item.get("owner", ""), "gate owner", 60, required=True, label=True)
        if owner not in exact_names:
            raise APIError("Every gate owner must name a crew member.")
        brief = item.get("brief", {})
        fields(brief, {"action", "facts", "why", "ifDecline", "undo", "source"})
        clean = {k: text(v, f"gate {k}", 2000) for k, v in brief.items() if k != "facts"}
        if "facts" in brief:
            facts = brief["facts"]
            if not isinstance(facts, list) or len(facts) > 12 or any(not isinstance(f, list) or len(f) != 2 for f in facts):
                raise APIError("Gate facts must be a list of pairs.")
            clean["facts"] = [[text(v, "gate fact", 500) for v in f] for f in facts]
        result["gates"].append({"owner": owner, "need": text(item.get("need", ""), "gate need", 2000, required=True), "brief": clean})
    return result


class Store:
    def __init__(self, directory):
        directory = Path(directory).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "office.sqlite3"
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS workspaces (id TEXT PRIMARY KEY, name TEXT NOT NULL, document TEXT NOT NULL)")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def connection(self, *, write=False):
        db = sqlite3.connect(str(self.path), timeout=15)
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get(db, ident):
        row = db.execute("SELECT document FROM workspaces WHERE id = ?", (ident,)).fetchone()
        if not row:
            raise APIError("Workspace not found.", 404)
        return json.loads(row[0])

    @staticmethod
    def save(db, item):
        db.execute("UPDATE workspaces SET name = ?, document = ? WHERE id = ?",
                   (item["name"], json.dumps(item, ensure_ascii=False), item["id"]))


class Handler(BaseHTTPRequestHandler):
    server_version = "OfficeStudio"
    sys_version = ""

    def log_message(self, *_args):
        pass  # Never log request paths, headers, bodies or provider keys.

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler uses this for malformed/unsupported HTTP too.
        self.close_connection = True
        self.json(code, {"error": self.responses.get(code, ("Request rejected",))[0]})

    def send_bytes(self, status, body, kind):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        policy = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        preview = getattr(self.server, "room_preview", None)
        if preview:
            hostname = self.headers.get("Host", "").split(":", 1)[0].lower()
            if hostname in ("127.0.0.1", "localhost"):
                policy += f"; frame-src http://{hostname}:{preview.port}"
                self.send_header("Permissions-Policy", f'screen-wake-lock=(self "http://{hostname}:{preview.port}")')
        else:
            policy += "; frame-src 'none'"
        self.send_header("Content-Security-Policy", policy)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, status, value):
        self.send_bytes(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8")

    def guard(self, *, post=False):
        hosts = self.headers.get_all("Host", [])
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.server.server_port == 80:
            allowed |= {"127.0.0.1", "localhost"}
        if len(hosts) != 1 or hosts[0].lower() not in allowed:
            raise APIError("This server accepts loopback Host headers only.", 403)
        if post:
            origins = self.headers.get_all("Origin", [])
            if len(origins) > 1 or (origins and origins[0].lower() not in {"http://" + hosts[0].lower()}):
                raise APIError("Cross-origin requests are not accepted.", 403)
            if self.headers.get("Sec-Fetch-Site", "").lower() not in ("", "same-origin", "none"):
                raise APIError("Cross-site requests are not accepted.", 403)

    def body(self):
        if self.headers.get("Transfer-Encoding"):
            raise APIError("Transfer encoding is not supported.", 400)
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,9}", lengths[0]):
            raise APIError("A valid Content-Length is required.", 411)
        size = int(lengths[0])
        if size > MAX_BODY:
            raise APIError("Request body is too large.", 413)
        if size < 2:
            raise APIError("A JSON object is required.")
        types = self.headers.get_all("Content-Type", [])
        if len(types) != 1 or types[0].split(";", 1)[0].strip().lower() != "application/json":
            raise APIError("Content-Type must be application/json.", 415)
        try:
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError()
            def no_constants(_value):
                raise ValueError()
            def unique_pairs(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError()
                    result[key] = value
                return result
            data = json.loads(raw.decode("utf-8"), parse_constant=no_constants, object_pairs_hook=unique_pairs)
        except (UnicodeError, ValueError, RecursionError):
            raise APIError("Invalid UTF-8 JSON object.") from None
        if not isinstance(data, dict):
            raise APIError("A JSON object is required.")
        return data

    def dispatch(self):
        self.guard(post=self.command == "POST")
        path = urlsplit(self.path).path
        store = self.server.store
        if self.command in ("GET", "HEAD"):
            room = re.fullmatch(rf"/api/workspaces/({ID})/room", path)
            if room:
                with store.connection() as db:
                    item = store.get(db, room[1])
                preview = self.server.room_preview
                hostname = self.headers["Host"].split(":", 1)[0].lower()
                self.json(200, {"url": preview.url(item, hostname) if preview else None})
                return
            if path == "/api/providers":
                self.json(200, {"providers": importlib.import_module("providers").list_providers()})
                return
            if path == "/api/workspaces":
                with store.connection() as db:
                    rows = db.execute("SELECT id, name FROM workspaces ORDER BY rowid DESC").fetchall()
                self.json(200, {"workspaces": [{"id": row[0], "name": row[1]} for row in rows]})
                return
            match = re.fullmatch(rf"/api/workspaces/({ID})", path)
            if match:
                with store.connection() as db:
                    item = store.get(db, match[1])
                self.json(200, item)
                return
            static = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"),
                      "/help.html": ("help.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
            pack = re.fullmatch(r"/packs/(re|law|acct|fin|med)\.json", path)
            target = static.get(path)
            if pack:
                target = (f"packs/{pack[1]}.json", "application/json; charset=utf-8")
            if target:
                try:
                    body = (ROOT / target[0]).read_bytes()
                except OSError:
                    raise APIError("File not found.", 404) from None
                self.send_bytes(200, body, target[1])
                return
            raise APIError("Not found.", 404)

        if self.command != "POST":
            raise APIError("Method not allowed.", 405)
        data = self.body()
        if path == "/api/workspaces":
            item = workspace(data)
            with store.connection(write=True) as db:
                if db.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0] >= MAX_WORKSPACES:
                    raise APIError("Workspace limit reached.", 409)
                db.execute("INSERT INTO workspaces VALUES (?, ?, ?)", (item["id"], item["name"], json.dumps(item, ensure_ascii=False)))
            self.json(201, item)
            return
        manual = re.fullmatch(rf"/api/workspaces/({ID})/manual", path)
        if manual:
            fields(data, {"url"})
            url = text(data.get("url"), "Manual URL", 2048, label=True)
            if url:
                try:
                    target = urlsplit(url)
                    valid = (target.scheme == "https" and target.hostname and target.username is None
                             and target.password is None and target.port != 0 and "\\" not in url
                             and not any(c.isspace() for c in url))
                except ValueError:
                    valid = False
                if not valid:
                    raise APIError("Enter an HTTPS manual link without embedded credentials.")
            with store.connection(write=True) as db:
                item = store.get(db, manual[1])
                item["manualUrl"] = url
                store.save(db, item)
            self.json(200, item)
            return
        appearance_match = re.fullmatch(rf"/api/workspaces/({ID})/agents/appearance", path)
        if appearance_match:
            fields(data, {"agent", "title", "color"})
            name = text(data.get("agent", ""), "agent", 60, required=True, label=True)
            appearance = {"title": text(data.get("title", ""), "title", 60, label=True),
                          "color": text(data.get("color", ""), "color", 7, label=True)}
            if appearance["color"] and not re.fullmatch(r"#[0-9A-Fa-f]{6}", appearance["color"]):
                raise APIError("color must be empty or a six-digit hex color.")
            with store.connection(write=True) as db:
                item = store.get(db, appearance_match[1])
                owner = next((a for a in item["crew"] if a["name"] == name), None)
                if owner is None:
                    raise APIError("Agent not found.", 404)
                owner["appearance"] = appearance
                store.save(db, item)
            self.json(200, item)
            return
        route_match = re.fullmatch(rf"/api/workspaces/({ID})/agents/route", path)
        if route_match:
            fields(data, {"agent", "provider", "model"})
            name = text(data.get("agent", ""), "agent", 60, required=True, label=True)
            providers = importlib.import_module("providers")
            try:
                routing = providers.resolve_route(data.get("provider"), data.get("model"))
            except providers.ProviderError as exc:
                raise APIError(str(exc), exc.status) from None
            with store.connection(write=True) as db:
                item = store.get(db, route_match[1])
                owner = next((a for a in item["crew"] if a["name"] == name), None)
                if owner is None:
                    raise APIError("Agent not found.", 404)
                owner["routing"] = routing
                store.save(db, item)
            self.json(200, item)
            return
        match = re.fullmatch(rf"/api/workspaces/({ID})/(agents|drafts)(?:/({ID})/decision)?", path)
        if not match:
            raise APIError("Not found.", 404)
        ident, action, draft_id = match.groups()
        if action == "agents" and draft_id:
            raise APIError("Not found.", 404)
        if action == "drafts" and not draft_id:
            fields(data, {"provider", "model", "agent", "brief"})
            name = text(data.get("agent", ""), "agent", 60, required=True, label=True)
            brief = text(data.get("brief", ""), "brief", 8000, required=True)
            with store.connection() as db:
                item = store.get(db, ident)
                owner = next((a for a in item["crew"] if a["name"] == name), None)
                if owner is None:
                    raise APIError("Agent not found.", 404)
                if len(item["drafts"]) >= MAX_DRAFTS:
                    raise APIError("Draft limit reached.", 409)
                instruction = owner["instruction"]
                if item["rules"]:
                    instruction += "\n\nWorkspace rules:\n" + item["rules"]
                saved = owner.get("routing") or {"provider": "demo", "model": ""}
                provider = data.get("provider", saved["provider"])
                model = data.get("model", None if "provider" in data else saved.get("model", ""))
            providers = importlib.import_module("providers")
            try:
                routing = providers.resolve_route(provider, model)
                generated = providers.generate_draft(routing["provider"], instruction, brief, model=routing["model"])
            except providers.ProviderError as exc:
                status = getattr(exc, "status", 502)
                raise APIError(str(exc), status if isinstance(status, int) and 400 <= status <= 599 else 502) from None
            if not isinstance(generated, str) or not generated.strip() or len(generated) > 100_000:
                raise APIError("Provider returned an invalid or oversized draft.", 502)
            with store.connection(write=True) as db:
                item = store.get(db, ident)
                if len(item["drafts"]) >= MAX_DRAFTS:
                    raise APIError("Draft limit reached.", 409)
                item["drafts"].append({"id": uuid.uuid4().hex, "agent": name, **routing,
                                       "brief": brief, "text": generated, "status": "pending"})
                store.save(db, item)
            self.json(201, item)
            return
        with store.connection(write=True) as db:
            item = store.get(db, ident)
            if action == "agents":
                new_agent = agent(data)
                if len(item["crew"]) >= 10:
                    raise APIError("All ten agent places are taken.", 409)
                if any(a["name"].casefold() == new_agent["name"].casefold() for a in item["crew"]):
                    raise APIError("Agent names must be unique.", 409)
                item["crew"].append(new_agent)
            else:
                fields(data, {"decision"})
                decision = data.get("decision")
                if decision not in ("approved", "declined"):
                    raise APIError("decision must be approved or declined.")
                draft = next((d for d in item["drafts"] if d["id"] == draft_id), None)
                if not draft:
                    raise APIError("Draft not found.", 404)
                if draft["status"] not in ("pending", decision):
                    raise APIError("This draft already has a different decision.", 409)
                draft["status"] = decision
            store.save(db, item)
        self.json(200, item)

    def handle_request(self):
        self.close_connection = True
        self.connection.settimeout(15)
        try:
            self.dispatch()
        except APIError as exc:
            self.json(exc.status, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            self.json(500, {"error": "The local server could not complete this request."})

    do_GET = do_HEAD = do_POST = do_OPTIONS = do_PUT = do_DELETE = do_PATCH = handle_request


class StudioServer(LoopbackHTTPServer):
    room_preview = None

    def server_close(self):
        if self.room_preview is not None:
            self.room_preview.close()
            self.room_preview = None
        super().server_close()


def create_server(port=8765, data_dir=None, room_file=None, room_port=0):
    """Construct a loopback server; port=0 is supported by in-process tests."""
    server = StudioServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    try:
        server.store = Store(data_dir if data_dir is not None else Path.home() / ".office-studio")
        if room_file is not None:
            from room_preview import RoomPreview
            def load_workspace(ident):
                with server.store.connection() as db:
                    try:
                        return server.store.get(db, ident)
                    except APIError as exc:
                        if exc.status == 404:
                            return None
                        raise
            server.room_preview = RoomPreview(room_file, load_workspace, server.server_port, room_port, check_logo=logo)
    except Exception:
        server.server_close()
        raise
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=Path.home() / ".office-studio")
    parser.add_argument("--room-file", type=Path, help="Owner-supplied local HTML room; never copied into this application")
    parser.add_argument("--room-port", type=int, default=0, help="Loopback room preview port (0 chooses a free port)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not 0 <= args.room_port <= 65535:
        parser.error("--room-port must be between 0 and 65535")
    try:
        server = create_server(args.port, args.data_dir, args.room_file, args.room_port)
    except (OSError, ValueError):
        parser.error("The local server or room preview could not start. Check the requested file and ports.")
    print(f"Office Studio: http://127.0.0.1:{server.server_port}", flush=True)
    print("Workspace storage stays on this computer. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
