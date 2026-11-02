"""Repeatable local HTTP checks: python -B -m unittest -v test_office.py.

Each test launches the actual CLI server against an outside-repository temporary
directory and an ephemeral loopback port. Live provider responses are mocked;
no model network requests are made.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
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
        self.process = subprocess.Popen(
            [sys.executable, "-B", str(ROOT / "server.py"), "--port", str(self.port), "--data-dir", self.sandbox.name],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=self.server_env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail("Server exited during startup: " + self.process.communicate()[0].decode("utf-8", "replace"))
            try:
                if self.request("GET", "/api/workspaces")[0] == 200:
                    return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.05)
        self.fail("Loopback server was not ready within ten seconds.")

    def stop_server(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process.communicate(timeout=5)
            self.process = None

    def request(self, method, route, data=None, headers=None):
        payload = None if data is None else json.dumps(data).encode("utf-8")
        combined = {"Content-Type": "application/json"} if data is not None else {}
        combined.update(headers or {})
        req = urllib.request.Request(self.base + route, data=payload, headers=combined, method=method)
        # Explicitly bypass environment proxies: test traffic remains loopback.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            response = opener.open(req, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            value = json.loads(body) if response.headers.get_content_type() == "application/json" else body.decode("utf-8")
            return response.status, value

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
        self.assertEqual([a["name"] for a in second["crew"]], [a["name"] for a in pack["crew"]])
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
        for route in ("/", "/index.html", "/app.js", "/style.css", "/packs/re.json", "/packs/law.json", "/packs/acct.json", "/packs/fin.json", "/packs/med.json"):
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
        self.assertEqual([a["routing"] for a in item["crew"]], [
            {"provider": "anthropic", "model": "fixture-claude"}, {"provider": "openai", "model": "fixture-openai-alt"}])
        sources = self.request("GET", "/api/providers")[1]["providers"]
        openai = next(p for p in sources if p["id"] == "openai")
        self.assertFalse(openai["configured"])
        self.assertEqual(openai["models"], ["fixture-openai-default", "fixture-openai-alt"])
        self.assertEqual(self.request("POST", base + "/drafts", {"agent": "HOST", "brief": "Fictional brief"})[0], 409)
        status, item = self.request("POST", base + "/drafts", {"agent": "HOST", "brief": "Fictional brief", "provider": "demo"})
        self.assertEqual(status, 201, item)
        self.assertEqual((item["drafts"][-1]["provider"], item["drafts"][-1]["model"]), ("demo", ""))
        self.assertEqual(item["crew"][1]["routing"], {"provider": "openai", "model": "fixture-openai-alt"})
        for route in ({"agent": "HOST", "provider": "openai", "model": "unlisted"},
                      {"agent": "HOST", "provider": "https://example.invalid", "model": "fixture-openai-alt"},
                      {"agent": "CRIMSON", "provider": "demo", "model": "wrong"}):
            self.assertEqual(self.request("POST", base + "/agents/route", route)[0], 400)
        self.assertEqual(self.request("POST", base + "/agents/route", {"agent": "MISSING", "provider": "demo", "model": ""})[0], 404)
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("GET", base)[1], item)


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
