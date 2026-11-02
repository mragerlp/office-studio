"""Repeatable local HTTP checks: python -B -m unittest -v test_office.py.

Each test launches the actual CLI server against an outside-repository temporary
directory and an ephemeral loopback port. Live provider responses are mocked;
no model network requests are made.
"""
from __future__ import annotations

import base64
from collections import deque
import http.client
import json
import os
from pathlib import Path
import socket
import re
import struct
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import zlib


ROOT = Path(__file__).resolve().parent


def png_logo(width=1, height=1, *, image_data=None):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    raw = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"\x00\x22\x66\xaa\xff") if image_data is None else image_data)
           + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


class OfficeHTTPTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix="office-studio-test-")
        self.addCleanup(self.sandbox.cleanup)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            self.port = reservation.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.process = None
        self.server_env = {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP", "USERPROFILE", "HOME") if name in os.environ}
        self.server_env.update({"OFFICE_OPENAI_MODEL": "fixture-openai-default", "OFFICE_OPENAI_MODELS": "fixture-openai-alt",
                                "OFFICE_ANTHROPIC_MODEL": "fixture-claude"})
        self.addCleanup(self.stop_server)
        self.start_server()

    def start_server(self):
        self.startup_started = time.monotonic()
        self.startup_events = deque(maxlen=20)
        self.startup_lock = threading.Lock()
        self.process = subprocess.Popen(
            [sys.executable, "-u", "-B", str(ROOT / "server.py"), "--port", str(self.port), "--data-dir", self.sandbox.name],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=self.server_env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.startup_reader = threading.Thread(target=self.capture_startup, args=(self.process.stdout,), daemon=True)
        self.startup_reader.start()
        deadline = self.startup_started + 10
        attempts, last_error = 0, "no connection attempted"
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.startup_reader.join(timeout=1)
                self.fail("Server exited during startup: " + self.startup_diagnostics(attempts, last_error))
            attempts += 1
            try:
                status = self.request("GET", "/api/workspaces", timeout=0.25)[0]
                if status == 200:
                    return
                last_error = f"HTTP {status}"
            except (OSError, http.client.HTTPException) as error:
                last_error = type(error).__name__
            time.sleep(0.05)
        self.fail("Loopback server was not ready within ten seconds. " + self.startup_diagnostics(attempts, last_error))

    def capture_startup(self, output):
        # Keep bounded timing evidence without echoing arbitrary child output,
        # request data, environment values or exception messages into CI logs.
        while raw := output.readline(2048):
            line = raw.decode("utf-8", "replace").strip()
            if re.fullmatch(r"Office Studio: http://127\.0\.0\.1:[0-9]+/?", line):
                safe = line
            elif line == "Workspace storage stays on this computer. Press Ctrl+C to stop.":
                safe = line
            else:
                kind = re.match(r"([A-Za-z][A-Za-z0-9_]*(?:Error|Exception)):", line)
                safe = (kind[1] + " (details omitted)") if kind else "[other startup output omitted]"
            with self.startup_lock:
                self.startup_events.append(f"+{time.monotonic() - self.startup_started:.3f}s {safe}")

    def startup_diagnostics(self, attempts, last_error):
        with self.startup_lock:
            captured = list(self.startup_events)
        status = self.process.poll()
        child = "running" if status is None else f"exit {status}"
        return (f"elapsed={time.monotonic() - self.startup_started:.3f}s; child={child}; "
                f"attempts={attempts}; last={last_error}; startup=" + (" | ".join(captured) or "[no startup output]"))

    def stop_server(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.startup_reader.join(timeout=1)
            self.process.stdout.close()
            self.process = None

    def request(self, method, route, data=None, headers=None, *, timeout=5):
        payload = None if data is None else json.dumps(data).encode("utf-8")
        combined = {"Content-Type": "application/json"} if data is not None else {}
        combined.update(headers or {})
        # Numeric HTTPConnection never consults urllib or macOS proxy settings.
        connection = http.client.HTTPConnection("127.0.0.1", urlsplit(self.base).port, timeout=timeout)
        try:
            connection.request(method, route, body=payload, headers=combined)
            response = connection.getresponse()
            body = response.read()
            kind = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
            value = json.loads(body) if kind == "application/json" else body.decode("utf-8")
            return response.status, value
        finally:
            connection.close()

    def restaurant(self, **changes):
        result = {
            "name": "Lantern Table", "town": "Example Town", "practice": "Restaurant",
            "color": "#d8582a", "logo": "", "rules": "Owner reviews every outgoing message.",
            "crew": [{"name": "CRIMSON", "specialty": "Coordination", "instruction": "Prepare fictional service plans for review."}],
            "gates": [{"owner": "CRIMSON", "need": "Approve a menu draft", "brief": {"action": "Record the owner's choice.", "ifDecline": "Keep the draft here."}}],
        }
        result.update(changes)
        return result

    def create(self, payload=None):
        status, item = self.request("POST", "/api/workspaces", payload or self.restaurant())
        self.assertEqual(status, 201, item)
        return item

    def draft(self, workspace, name="CRIMSON"):
        status, item = self.request("POST", f"/api/workspaces/{workspace['id']}/drafts", {
            "provider": "demo", "agent": name, "brief": "Prepare a fictional welcome for owner review; do not send it.",
        })
        self.assertEqual(status, 201, item)
        result = item["drafts"][-1]
        self.assertEqual((result["agent"], result["provider"], result["status"]), (name, "demo", "pending"))
        self.assertTrue(result["text"].strip())
        return item, result

    def test_two_businesses_tasks_and_restart_persistence(self):
        first = self.create()
        pack = json.loads((ROOT / "packs" / "re.json").read_text(encoding="utf-8"))
        second = self.create({"name": "Example Realty Studio", "town": "Sample Borough", "color": "#235c88", "logo": png_logo(),
                              "practice": pack["practice"], "crew": pack["crew"], "gates": pack["gates"], "rules": pack["rules"]})
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["practice"], "Restaurant")
        self.assertEqual([a["name"] for a in second["crew"]], [a["name"] for a in pack["crew"]] + ["LEGAL"])
        status, first = self.request("POST", f"/api/workspaces/{first['id']}/agents", {
            "name": "HOST", "specialty": "Reservations", "instruction": "Prepare fictional reservation replies for owner review.",
        })
        self.assertEqual(status, 200, first)
        self.assertEqual(first["crew"][-1]["name"], "HOST")
        first, draft = self.draft(first, "HOST")
        status, first = self.request("POST", f"/api/workspaces/{first['id']}/drafts/{draft['id']}/decision", {"decision": "approved"})
        self.assertEqual(status, 200, first)
        self.assertEqual(first["drafts"][-1]["status"], "approved")
        self.assertEqual(self.request("GET", f"/api/workspaces/{second['id']}")[1], second)
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("GET", f"/api/workspaces/{first['id']}")[1], first)
        self.assertEqual(self.request("GET", f"/api/workspaces/{second['id']}")[1], second)
        self.assertEqual({w["id"] for w in self.request("GET", "/api/workspaces")[1]["workspaces"]}, {first["id"], second["id"]})
        self.assertTrue((Path(self.sandbox.name) / "office.sqlite3").is_file())

    def test_decisions_are_pending_only_and_idempotent(self):
        item = self.create()
        for decision, competing in (("approved", "declined"), ("declined", "approved")):
            item, draft = self.draft(item)
            route = f"/api/workspaces/{item['id']}/drafts/{draft['id']}/decision"
            status, decided = self.request("POST", route, {"decision": decision})
            self.assertEqual(status, 200, decided)
            self.assertEqual(decided["drafts"][-1]["status"], decision)
            self.assertEqual(self.request("POST", route, {"decision": decision}), (200, decided))
            self.assertEqual(self.request("POST", route, {"decision": competing})[0], 409)
            self.assertEqual(self.request("GET", f"/api/workspaces/{item['id']}")[1], decided)
            item = decided

    def test_company_manual_is_an_optional_per_office_https_link(self):
        _, office = self.request("POST", "/api/workspaces", self.restaurant())
        _, other = self.request("POST", "/api/workspaces", self.restaurant(name="Other office"))
        route = "/api/workspaces/" + office["id"]
        url = "https://example.org/office-manual#map"
        self.assertEqual(self.request("POST", route + "/manual", {"url": url})[1]["manualUrl"], url)
        for unsafe in ("javascript:alert(1)", "http://example.org", "https://user:pass@example.org", "https://example.org\\@elsewhere"):
            self.assertEqual(self.request("POST", route + "/manual", {"url": unsafe})[0], 400)
        self.assertEqual(self.request("GET", route)[1]["manualUrl"], url)
        self.assertEqual(self.request("GET", "/api/workspaces/" + other["id"])[1]["manualUrl"], "")
        self.assertEqual(self.request("POST", route + "/manual", {"url": ""})[1]["manualUrl"], "")
        status, guide = self.request("GET", "/help.html")
        self.assertEqual(status, 200)
        self.assertIn("Your company's manual", guide)

    def test_workspace_references_do_not_cross(self):
        first, draft = self.draft(self.create())
        second = self.create(self.restaurant(name="Fictional Second Business", crew=[{"name": "OTHER", "specialty": "Second lane", "instruction": "Work only in this fictional business."}], gates=[]))
        self.assertEqual(self.request("POST", f"/api/workspaces/{second['id']}/drafts/{draft['id']}/decision", {"decision": "approved"})[0], 404)
        self.assertEqual(self.request("POST", f"/api/workspaces/{second['id']}/drafts", {"provider": "demo", "agent": "CRIMSON", "brief": "Fictional task"})[0], 404)
        self.assertEqual(self.request("GET", f"/api/workspaces/{first['id']}")[1], first)
        self.assertEqual(self.request("GET", f"/api/workspaces/{second['id']}")[1], second)

    def test_logos_reject_remote_active_malformed_and_oversized_images(self):
        invalid = ["https://example.invalid/logo.png", "file:///private/logo.png", "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
                   "data:image/png;base64," + base64.b64encode(b"not a PNG").decode(), png_logo(5000, 1), png_logo(image_data=b"not-zlib"),
                   "data:image/png;base64," + "A" * 700_001]
        for value in invalid:
            with self.subTest(logo_kind=value[:40]):
                self.assertEqual(self.request("POST", "/api/workspaces", self.restaurant(logo=value))[0], 400)
        self.assertEqual(self.request("GET", "/api/workspaces")[1], {"workspaces": []})
        good = self.create(self.restaurant(logo=png_logo()))
        self.assertEqual(good["logo"], png_logo())

    def test_host_origin_and_static_route_boundaries(self):
        for host in ("example.invalid", f"127.0.0.1:{self.port + 1}", f"127.0.0.1.example.invalid:{self.port}"):
            self.assertEqual(self.request("GET", "/api/workspaces", headers={"Host": host})[0], 403)
        for origin in ("https://example.invalid", "null", f"http://localhost:{self.port}"):
            self.assertEqual(self.request("POST", "/api/workspaces", self.restaurant(), {"Origin": origin})[0], 403)
        self.assertEqual(self.request("POST", "/api/workspaces", self.restaurant(), {"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.create(self.restaurant(name="Same origin allowed"))
        self.assertEqual(self.request("POST", "/api/workspaces", self.restaurant(name="Explicit origin"), {"Origin": self.base})[0], 201)
        for route in ("/server.py", "/providers.py", "/test_office.py", "/../server.py", "/%2e%2e/server.py", "/office.sqlite3"):
            self.assertEqual(self.request("GET", route)[0], 404, route)

    def test_normal_static_routes_and_provider_status(self):
        for route in ("/", "/index.html", "/help.html", "/app.js", "/style.css", "/assets/ampersand.svg", "/packs/re.json", "/packs/law.json", "/packs/acct.json", "/packs/fin.json", "/packs/med.json"):
            status, body = self.request("GET", route)
            self.assertEqual(status, 200, route)
            self.assertTrue(body, route)
        status, data = self.request("GET", "/api/providers")
        self.assertEqual(status, 200, data)
        demo = next(p for p in data["providers"] if p["id"] == "demo")
        self.assertTrue(demo["configured"])

    def test_independent_routes_persist_without_credentials_and_demo_stays_available(self):
        item = self.create()
        base = f"/api/workspaces/{item['id']}"
        status, item = self.request("POST", base + "/agents", {"name": "HOST", "specialty": "Service", "instruction": "Prepare a fictional greeting."})
        self.assertEqual(status, 200)
        for name, provider, model in (("CRIMSON", "anthropic", "fixture-claude"), ("HOST", "openai", "fixture-openai-alt")):
            status, item = self.request("POST", base + "/agents/route", {"agent": name, "provider": provider, "model": model})
            self.assertEqual(status, 200, item)
        routes = {a["name"]: a["routing"] for a in item["crew"]}
        self.assertEqual(routes, {"CRIMSON": {"provider": "anthropic", "model": "fixture-claude"},
                                 "LEGAL": {"provider": "demo", "model": ""},
                                 "HOST": {"provider": "openai", "model": "fixture-openai-alt"}})
        sources = self.request("GET", "/api/providers")[1]["providers"]
        openai = next(p for p in sources if p["id"] == "openai")
        self.assertFalse(openai["configured"])
        self.assertEqual(openai["models"], ["fixture-openai-default", "fixture-openai-alt"])
        self.assertEqual(self.request("POST", base + "/drafts", {"agent": "HOST", "brief": "Fictional brief"})[0], 409)
        status, item = self.request("POST", base + "/drafts", {"agent": "HOST", "brief": "Fictional brief", "provider": "demo"})
        self.assertEqual(status, 201, item)
        self.assertEqual((item["drafts"][-1]["provider"], item["drafts"][-1]["model"]), ("demo", ""))
        self.assertEqual(next(a for a in item["crew"] if a["name"] == "HOST")["routing"], {"provider": "openai", "model": "fixture-openai-alt"})
        for route in ({"agent": "HOST", "provider": "openai", "model": "unlisted"},
                      {"agent": "HOST", "provider": "https://example.invalid", "model": "fixture-openai-alt"},
                      {"agent": "CRIMSON", "provider": "demo", "model": "wrong"}):
            self.assertEqual(self.request("POST", base + "/agents/route", route)[0], 400)
        self.assertEqual(self.request("POST", base + "/agents/route", {"agent": "MISSING", "provider": "demo", "model": ""})[0], 404)
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("GET", base)[1], item)

    def test_all_five_pack_sources_gain_one_canonical_legal_without_source_edits(self):
        from room_preview import renderer_pack
        status, canonical = self.request("GET", "/api/templates/legal")
        self.assertEqual(status, 200, canonical)
        self.assertEqual((canonical["name"], canonical["specialty"], canonical["engine"], canonical["color"], canonical["style"]),
                         ("LEGAL", "Legal Review", "Local demo", "indigo", "vest"))
        self.assertIn("qualified counsel", canonical["instruction"])
        self.assertIn("owner approval", canonical["instruction"])
        self.assertNotIn("routing", canonical)
        for key in ("re", "law", "acct", "fin", "med"):
            with self.subTest(pack=key):
                source = ROOT / "packs" / f"{key}.json"
                original = source.read_bytes()
                pack = json.loads(original)
                item = self.create(self.restaurant(name="Fictional " + key, practice=pack["practice"], crew=pack["crew"],
                                                   gates=pack["gates"], rules=pack["rules"]))
                self.assertEqual([a["name"] for a in item["crew"]], [a["name"] for a in pack["crew"]] + ["LEGAL"])
                legal = item["crew"][-1]
                self.assertEqual({field: legal[field] for field in canonical}, canonical)
                self.assertEqual(sum(a["name"].casefold() == "legal" for a in item["crew"]), 1)
                self.assertEqual(item["gates"], pack["gates"])
                rendered = renderer_pack(item)
                self.assertIsNotNone(rendered)
                names = {a["name"] for a in rendered["crew"]}
                self.assertTrue(all(g["owner"] in names for g in rendered["gates"]))
                self.assertEqual(source.read_bytes(), original)

    def test_legal_reservation_never_evicts_or_duplicates_user_desks(self):
        crew = [{"name": "CRIMSON" if i == 0 else f"DESK{i}", "specialty": "Fictional lane", "instruction": "Prepare a fictional draft."}
                for i in range(10)]
        status, error = self.request("POST", "/api/workspaces", self.restaurant(crew=crew, gates=[]))
        self.assertEqual(status, 400, error)
        self.assertIn("Legal", error["error"])
        self.assertEqual(self.request("GET", "/api/workspaces")[1], {"workspaces": []})
        item = self.create(self.restaurant(crew=crew[:9], gates=[]))
        self.assertEqual([a["name"] for a in item["crew"]], [a["name"] for a in crew[:9]] + ["LEGAL"])
        self.assertEqual(len(item["crew"]), 10)
        for name in ("LEGAL", "Legal", "legal"):
            with self.subTest(name=name):
                supplied = [dict(a) for a in crew]
                supplied[4] = {"name": name, "specialty": "Owner's legal lane", "instruction": "Prepare owner-selected questions for counsel."}
                saved = self.create(self.restaurant(crew=supplied, gates=[]))
                self.assertEqual([a["name"] for a in saved["crew"]], [a["name"] for a in supplied])
                self.assertEqual(saved["crew"][4]["specialty"], supplied[4]["specialty"])
                self.assertEqual(saved["crew"][4]["instruction"], supplied[4]["instruction"])
                self.assertEqual(len(saved["crew"]), 10)

    def test_legacy_persisted_office_is_not_changed_on_restart_or_read(self):
        import server
        legacy = self.restaurant()
        legacy.update({"id": "a" * 32, "drafts": [], "manualUrl": ""})
        self.stop_server()
        store = server.Store(self.sandbox.name)
        with store.connection(write=True) as db:
            db.execute("INSERT INTO workspaces VALUES (?, ?, ?)", (legacy["id"], legacy["name"], json.dumps(legacy)))
        self.start_server()
        self.assertEqual(self.request("GET", f"/api/workspaces/{legacy['id']}")[1], legacy)
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("GET", f"/api/workspaces/{legacy['id']}")[1], legacy)


class LoopbackBindingTests(unittest.TestCase):
    def test_numeric_loopback_bind_never_calls_reverse_dns(self):
        import server
        with tempfile.TemporaryDirectory(prefix="office-bind-") as directory, patch.object(socket, "getfqdn", side_effect=AssertionError("reverse lookup must not run")) as lookup:
            httpd = server.create_server(0, directory)
            try:
                self.assertEqual(httpd.server_name, "127.0.0.1")
                self.assertEqual(httpd.server_port, httpd.socket.getsockname()[1])
                lookup.assert_not_called()
            finally:
                httpd.server_close()

    def test_optional_room_bind_never_calls_reverse_dns(self):
        import server
        with tempfile.TemporaryDirectory(prefix="office-room-bind-") as directory, patch.object(socket, "getfqdn", side_effect=AssertionError("reverse lookup must not run")) as lookup:
            room = Path(directory) / "synthetic-room.html"
            room.write_text("<!doctype html><title>Synthetic local room</title>", encoding="utf-8")
            httpd = server.create_server(0, Path(directory) / "storage", room_file=room)
            try:
                preview = httpd.room_preview.httpd
                self.assertEqual(preview.server_name, "127.0.0.1")
                self.assertEqual(preview.server_port, preview.socket.getsockname()[1])
                self.assertNotEqual(preview.server_port, httpd.server_port)
                lookup.assert_not_called()
            finally:
                httpd.server_close()


class RoutedDraftTests(unittest.TestCase):
    request = OfficeHTTPTests.request
    create = OfficeHTTPTests.create
    restaurant = OfficeHTTPTests.restaurant

    def test_saved_and_explicit_routes_use_allowed_models_and_workspace_rules(self):
        import providers
        import server
        environment = {"OPENAI_API_KEY": "test-fixture-value", "OFFICE_OPENAI_MODEL": "fixture-default",
                       "OFFICE_OPENAI_MODELS": "fixture-alt", "ANTHROPIC_API_KEY": "test-fixture-value",
                       "OFFICE_ANTHROPIC_MODEL": "fixture-claude"}
        with tempfile.TemporaryDirectory(prefix="office-studio-route-") as directory, patch.dict(os.environ, environment, clear=True):
            httpd = server.create_server(0, directory)
            worker = threading.Thread(target=httpd.serve_forever, daemon=True)
            worker.start()
            self.base = f"http://127.0.0.1:{httpd.server_port}"
            try:
                item = self.create()
                base = f"/api/workspaces/{item['id']}"
                status, item = self.request("POST", base + "/agents", {"name": "HOST", "specialty": "Service", "instruction": "Prepare a fictional greeting."})
                self.assertEqual(status, 200)
                # Existing agents without routing remain usable as local demos.
                with httpd.store.connection(write=True) as db:
                    legacy = httpd.store.get(db, item["id"])
                    for person in legacy["crew"]:
                        person.pop("routing", None)
                    httpd.store.save(db, legacy)
                with patch.object(providers, "_post") as post:
                    status, item = self.request("POST", base + "/drafts", {"agent": "CRIMSON", "brief": "Fictional brief"})
                    self.assertEqual(status, 201, item)
                    self.assertEqual(item["drafts"][-1]["model"], "")
                    post.assert_not_called()
                for name, source, model in (("CRIMSON", "anthropic", "fixture-claude"), ("HOST", "openai", "fixture-alt")):
                    self.assertEqual(self.request("POST", base + "/agents/route", {"agent": name, "provider": source, "model": model})[0], 200)
                responses = {
                    "api.openai.com": {"output": [{"type": "message", "content": [{"type": "output_text", "text": "Fictional draft"}]}]},
                    "api.anthropic.com": {"content": [{"type": "text", "text": "Fictional draft"}]}}
                with patch.object(providers, "_post", side_effect=lambda host, *args: responses[host]) as post:
                    for name, extra, source, model in (("CRIMSON", {}, "anthropic", "fixture-claude"),
                                                       ("HOST", {}, "openai", "fixture-alt"),
                                                       ("HOST", {"provider": "openai"}, "openai", "fixture-default"),
                                                       ("CRIMSON", {"provider": "openai", "model": "fixture-alt"}, "openai", "fixture-alt")):
                        status, item = self.request("POST", base + "/drafts", {"agent": name, "brief": "Fictional brief", **extra})
                        self.assertEqual(status, 201, item)
                        draft = item["drafts"][-1]
                        self.assertEqual((draft["provider"], draft["model"], draft["status"]), (source, model, "pending"))
                        payload = post.call_args.args[3]
                        self.assertEqual(payload["model"], model)
                        system = payload.get("instructions", payload.get("system"))
                        self.assertIn(item["rules"], system)
                        self.assertIn(next(a["instruction"] for a in item["crew"] if a["name"] == name), system)
                    before = post.call_count
                    self.assertEqual(self.request("POST", base + "/drafts", {"agent": "HOST", "brief": "Fictional brief", "model": "unlisted"})[0], 400)
                    self.assertEqual(post.call_count, before)
            finally:
                httpd.shutdown()
                httpd.server_close()
                worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
