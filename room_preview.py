"""Isolated, optional preview of an owner's explicit local HTML room file.

The source stays outside this distribution. Only a minimal simulated pack crosses
into the preview origin; provider configuration and drafting records stay out.
"""
import json
from pathlib import Path
import re
import threading
from http.server import BaseHTTPRequestHandler

from loopback_server import LoopbackHTTPServer


STYLES = {"headset", "blazer", "hoodie", "field", "vest", "site", "press", "robot"}
COLORS = {"crimson", "orange", "violet", "teal", "azure", "green", "lime", "plum", "indigo", "aqua", "slate", "olive"}
KEY = r"[0-9a-f]{32}"
THREE = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"


def clean_text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        return None
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        return None
    return value.strip()


def systems(value):
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:20]:
        name = clean_text(item, 100)
        if name and "\n" not in name and "\t" not in name and name not in result:
            result.append(name)
    return result


def renderer_pack(workspace):
    """Return None for incompatible crews; never rename or invent an agent."""
    if not isinstance(workspace, dict):
        return None
    title = clean_text(workspace.get("name"), 120)
    crew = workspace.get("crew")
    if not title or not isinstance(crew, list) or not 1 <= len(crew) <= 10:
        return None
    exported, names, sources = [], set(), []
    for position, person in enumerate(crew):
        if not isinstance(person, dict):
            return None
        name = person.get("name")
        specialty = clean_text(person.get("specialty"), 120)
        instruction = clean_text(person.get("instruction"), 4000)
        if not isinstance(name, str) or not re.fullmatch(r"[A-Z][A-Z0-9 -]{0,13}", name) or name != name.strip():
            return None
        if name in names or (position == 0 and name != "CRIMSON") or not specialty or not instruction:
            return None
        names.add(name)
        labels = systems(person.get("systems"))
        for label in labels:
            if label not in sources and len(sources) < 20:
                sources.append(label)
        color, style = person.get("color"), person.get("style")
        exported.append({"name": name, "specialty": specialty, "instruction": instruction,
                         "engine": clean_text(person.get("engine"), 100) or "Local demo",
                         "color": "crimson" if position == 0 else color if isinstance(color, str) and color in COLORS else "azure",
                         "style": style if isinstance(style, str) and style in STYLES else "headset", "systems": labels})
    gates = workspace.get("gates", [])
    if not isinstance(gates, list) or len(gates) > 40:
        return None
    approvals = []
    for gate in gates:
        if not isinstance(gate, dict) or not isinstance(gate.get("owner"), str) or gate["owner"] not in names:
            return None
        need = clean_text(gate.get("need"), 2000)
        brief = gate.get("brief", {})
        if not need or not isinstance(brief, dict):
            return None
        approvals.append({"owner": gate["owner"], "need": need, "brief": {
            "action": clean_text(brief.get("action"), 2000) or "Review this prepared item. No external action is performed.",
            "ifDecline": clean_text(brief.get("ifDecline"), 2000) or "Keep this item held for owner review."}})
    return {"office": title, "feed": "simulated", "rules": clean_text(workspace.get("rules"), 8000) or
            "Simulated room only. Prepare drafts for owner review; perform no external actions.",
            "systems": sources, "crew": exported, "gates": approvals}


class PreviewHandler(BaseHTTPRequestHandler):
    server_version = "OfficeRoom"
    sys_version = ""

    def log_message(self, *_args):
        pass

    def reply(self, status, body, content_type="application/json; charset=utf-8", key=None, hostname=None):
        policy = "default-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        if key and hostname:
            origin = f"http://{hostname}:{self.server.server_port}"
            parent = f"http://{hostname}:{self.server.preview.studio_port}"
            policy = (f"default-src 'none'; script-src 'unsafe-inline' {THREE}; style-src 'unsafe-inline'; "
                      f"img-src data:; font-src data:; connect-src {origin}/packs/{key}.json; "
                      f"object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors {parent}")
            self.send_response(status)
            self.send_header("Permissions-Policy", "screen-wake-lock=(self)")
        else:
            self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", policy)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def fail(self, status):
        self.reply(status, json.dumps({"error": self.responses.get(status, ("Request rejected",))[0]}).encode())

    def send_error(self, code, message=None, explain=None):
        self.close_connection = True
        self.fail(code)

    def dispatch(self):
        hosts = self.headers.get_all("Host", [])
        allowed = {f"127.0.0.1:{self.server.server_port}": "127.0.0.1", f"localhost:{self.server.server_port}": "localhost"}
        if self.server.server_port == 80:
            allowed.update({"127.0.0.1": "127.0.0.1", "localhost": "localhost"})
        if len(hosts) != 1 or hosts[0].lower() not in allowed:
            self.fail(403)
            return
        if self.command != "GET":
            self.fail(405)
            return
        hostname = allowed[hosts[0].lower()]
        page = re.fullmatch(rf"/(?:room/index\.html|examples/iv-therapy/index\.html)\?pack=({KEY})(?:&view=overview)?", self.path)
        data = re.fullmatch(rf"/packs/({KEY})\.json", self.path)
        if not (page or data):
            self.fail(404)
            return
        key = (page or data)[1]
        preview = self.server.preview
        if (hostname, key) not in preview.issued:
            self.fail(404)
            return
        pack = preview.pack(key)
        if pack is None:
            self.fail(404)
            return
        if page:
            self.reply(200, preview.themed_html(key, hostname), "text/html; charset=utf-8", key, hostname)
        else:
            self.reply(200, json.dumps(pack, ensure_ascii=False, allow_nan=False).encode("utf-8"))

    def handle_request(self):
        self.close_connection = True
        self.connection.settimeout(10)
        try:
            self.dispatch()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            self.fail(500)

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = handle_request


class RoomPreview:
    def __init__(self, room_file, load_workspace, studio_port, port=0, *, check_logo=None):
        source = Path(room_file).expanduser()
        if source.suffix.lower() not in (".html", ".htm") or not source.is_file() or source.stat().st_size > 16_777_216:
            raise ValueError("A local HTML room file of at most 16 MB is required.")
        self.html = source.read_bytes()
        if not self.html or len(self.html) > 16_777_216:
            raise ValueError("A nonempty local HTML room file of at most 16 MB is required.")
        self.load_workspace = load_workspace
        self.check_logo = check_logo
        self.theme = Path(__file__).with_name("room_theme.js").read_text(encoding="utf-8")
        self.studio_port = studio_port
        self.issued = set()
        self.httpd = LoopbackHTTPServer(("127.0.0.1", port), PreviewHandler)
        self.httpd.daemon_threads = True
        self.httpd.preview = self
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="office-room-preview", daemon=True)
        self.thread.start()

    @property
    def port(self):
        return self.httpd.server_port

    def pack(self, key):
        return renderer_pack(self.load_workspace(key))

    def themed_html(self, key, hostname):
        workspace = self.load_workspace(key)
        # This presentation allowlist is separate from the renderer's identity
        # pack. Stored strings are JSON text, never executable markup or code.
        brand_color = workspace.get("color", "")
        if not isinstance(brand_color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", brand_color):
            brand_color = "#285b53"
        checked_logo = ""
        if self.check_logo:
            try:
                checked_logo = self.check_logo(workspace.get("logo", ""))
            except Exception:
                pass
        agents = []
        for person in workspace["crew"]:
            appearance = person.get("appearance", {})
            if not isinstance(appearance, dict):
                appearance = {}
            color = appearance.get("color", "")
            if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                color = brand_color if person["name"] == "CRIMSON" else ""
            default_title = "Head Executive" if person["name"] == "CRIMSON" else (
                "Legal Review" if person["name"].casefold() == "legal" else person["name"])
            agents.append({"agent": person["name"], "title": clean_text(appearance.get("title"), 60) or default_title, "color": color})
        presentation = {"name": workspace["name"], "color": brand_color, "logo": checked_logo, "agents": agents,
                        "studioOrigin": f"http://{hostname}:{self.studio_port}"}
        encoded = json.dumps(presentation, ensure_ascii=True, allow_nan=False)
        for character, escape in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
            encoded = encoded.replace(character, escape)
        injection = ('<script type="application/json" id="office-studio-presentation">' + encoded +
                     '</script><script data-office-theme-adapter="1">' + self.theme + '</script>').encode("utf-8")
        closing = self.html.lower().rfind(b"</body>")
        return self.html[:closing] + injection + self.html[closing:] if closing >= 0 else self.html + injection

    def url(self, workspace, hostname):
        if hostname not in ("127.0.0.1", "localhost") or renderer_pack(workspace) is None:
            return None
        key = workspace.get("id")
        if not isinstance(key, str) or not re.fullmatch(KEY, key):
            return None
        self.issued.add((hostname, key))
        return f"http://{hostname}:{self.port}/room/index.html?pack={key}&view=overview"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
