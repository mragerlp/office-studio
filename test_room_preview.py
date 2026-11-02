"""Local-only room isolation checks using an original, temporary HTML fixture."""
import http.client
import json
import re
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlsplit

import server


class RoomPreviewTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix="office-room-test-")
        self.addCleanup(self.sandbox.cleanup)
        self.html = b"<!doctype html><title>Owner room fixture</title><p>Local synthetic room.</p>\r\n"
        self.source = Path(self.sandbox.name) / "owner-room.html"
        self.source.write_bytes(self.html)
        self.httpd = server.create_server(0, Path(self.sandbox.name) / "storage", room_file=self.source)
        self.worker = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.worker.join(timeout=5)

    def request(self, path, *, port=None, method="GET", body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", port or self.httpd.server_port, timeout=5)
        encoded = None if body is None else json.dumps(body)
        supplied = {"Content-Type": "application/json"} if body is not None else {}
        supplied.update(headers or {})
        conn.request(method, path, encoded, supplied)
        response = conn.getresponse()
        raw = response.read()
        result = json.loads(raw) if raw and response.headers.get_content_type() == "application/json" else raw
        status, received = response.status, dict(response.headers)
        conn.close()
        return status, result, received

    def create(self, crew=None, **extra):
        body = {"name": "Fictional Studio", "practice": "General business", "rules": "", "gates": [],
                "crew": crew or [{"name": "CRIMSON", "specialty": "Coordination", "instruction": "Prepare fictional plans."}], **extra}
        status, item, _ = self.request("/api/workspaces", method="POST", body=body)
        self.assertEqual(status, 201, item)
        return item

    def room(self, item, host=None):
        headers = {} if host is None else {"Host": f"{host}:{self.httpd.server_port}"}
        status, data, _ = self.request(f"/api/workspaces/{item['id']}/room", headers=headers)
        self.assertEqual(status, 200, data)
        return urlsplit(data["url"]) if data["url"] else None

    def test_original_bytes_and_minimal_generic_pack(self):
        item = self.create(town="Synthetic Town")
        with self.httpd.store.connection(write=True) as db:
            saved = self.httpd.store.get(db, item["id"])
            saved["drafts"] = [{"text": "private drafting fixture"}]
            saved["crew"][0]["routing"] = {"provider": "openai", "model": "private-model-fixture"}
            self.httpd.store.save(db, saved)
        frame = self.room(item)
        self.assertEqual(frame.hostname, "127.0.0.1")
        self.assertNotEqual(frame.port, self.httpd.server_port)
        self.assertEqual(frame.query, f"pack={item['id']}&view=overview")
        status, raw, headers = self.request(frame.path + "?" + frame.query, port=frame.port)
        self.assertEqual(status, 200)
        self.assertTrue(raw.startswith(self.html))
        self.assertIn(b'data-office-theme-adapter="1"', raw)
        policy = headers["Content-Security-Policy"]
        self.assertIn(f"frame-ancestors http://127.0.0.1:{self.httpd.server_port}", policy)
        self.assertIn(f"connect-src http://127.0.0.1:{frame.port}/packs/{item['id']}.json", policy)
        self.assertIn("https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js", policy)
        self.assertEqual(headers["Permissions-Policy"], "screen-wake-lock=(self)")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        status, pack, _ = self.request(f"/packs/{item['id']}.json", port=frame.port)
        self.assertEqual(status, 200)
        self.assertEqual(set(pack), {"office", "feed", "rules", "systems", "crew", "gates"})
        self.assertEqual(pack["office"], item["name"])
        self.assertTrue(pack["rules"].strip())
        self.assertEqual(pack["crew"][0]["engine"], "Local demo")
        self.assertEqual(pack["crew"][0]["style"], "headset")
        self.assertEqual(pack["crew"][0]["color"], "crimson")
        self.assertNotIn("private", json.dumps(pack))
        self.assertEqual(self.source.read_bytes(), self.html)
        self.assertEqual(self.request("/", headers={})[0], 200)

    def test_all_shipped_packs_and_missing_brief_fields_are_adapted(self):
        for key in ("re", "law", "acct", "fin", "med"):
            pack = json.loads((server.ROOT / "packs" / f"{key}.json").read_text(encoding="utf-8"))
            item = self.create(crew=pack["crew"], gates=pack["gates"], rules=pack["rules"])
            frame = self.room(item)
            self.assertIsNotNone(frame, key)
            exported = self.request(f"/packs/{item['id']}.json", port=frame.port)[1]
            self.assertEqual([a["name"] for a in exported["crew"]], [a["name"] for a in pack["crew"]] + ["LEGAL"])
            self.assertEqual(exported["rules"], pack["rules"])
        item = self.create(gates=[{"owner": "CRIMSON", "need": "Review fictional item", "brief": {}}])
        frame = self.room(item)
        exported = self.request(f"/packs/{item['id']}.json", port=frame.port)[1]
        self.assertTrue(exported["gates"][0]["brief"]["action"])
        self.assertTrue(exported["gates"][0]["brief"]["ifDecline"])

    def test_incompatible_roster_is_not_renamed(self):
        for name in ("OWNER", "Crimson", "CRIMSON-LONG-NAME"):
            item = self.create(crew=[{"name": name, "specialty": "Coordination", "instruction": "Prepare fictional plans."}])
            self.assertIsNone(self.room(item))
            saved = self.request(f"/api/workspaces/{item['id']}")[1]
            self.assertEqual(saved["crew"][0]["name"], name)

    def test_routes_queries_hosts_and_workspace_boundaries_fail_closed(self):
        item = self.create()
        frame = self.room(item)
        other = self.create(name="Other fictional office")
        good = frame.path + "?" + frame.query
        for path in ("/", "/server.py", "/room/index.html", "/examples/iv-therapy/index.html", "/packs/re.json",
                     good + "&bridge=ws://example.invalid", good + "&pack=" + item["id"],
                     f"/room/index.html?pack={item['id']}&view=desks",
                     "/room/index.html?pack=../x", "/%2e%2e/server.py", f"/packs/{other['id']}.json",
                     "/packs/" + "0" * 32 + ".json", f"/packs/{item['id']}.json?bridge=x"):
            self.assertGreaterEqual(self.request(path, port=frame.port)[0], 400, path)
        self.assertEqual(self.request(good, port=frame.port, headers={"Host": "example.invalid"})[0], 403)
        self.assertEqual(self.request(good, port=frame.port, method="POST", body={})[0], 405)
        self.assertEqual(self.request(good, port=frame.port, method="HEAD")[0], 405)
        self.assertEqual(self.request(f"/examples/iv-therapy/index.html?pack={item['id']}", port=frame.port)[0], 200)
        self.assertEqual(self.request("/api/workspaces/" + "0" * 32 + "/room")[0], 404)

    def test_localhost_origin_and_parent_frame_policy(self):
        item = self.create()
        frame = self.room(item, "localhost")
        self.assertEqual(frame.hostname, "localhost")
        status, _, headers = self.request(frame.path + "?" + frame.query, port=frame.port,
                                          headers={"Host": f"localhost:{frame.port}"})
        self.assertEqual(status, 200)
        self.assertIn(f"frame-ancestors http://localhost:{self.httpd.server_port}", headers["Content-Security-Policy"])
        _, _, parent_headers = self.request("/", headers={"Host": f"localhost:{self.httpd.server_port}"})
        self.assertIn(f"frame-src http://localhost:{frame.port}", parent_headers["Content-Security-Policy"])
        self.assertEqual(parent_headers["Permissions-Policy"], f'screen-wake-lock=(self "http://localhost:{frame.port}")')
        raw = self.request(frame.path + "?" + frame.query, port=frame.port, headers={"Host": f"localhost:{frame.port}"})[1]
        self.assertEqual(self.presentation(raw)["studioOrigin"], f"http://localhost:{self.httpd.server_port}")

    @staticmethod
    def presentation(html):
        match = re.search(rb'<script type="application/json" id="office-studio-presentation">(.*?)</script>', html, re.S)
        return json.loads(match[1])

    def test_appearance_preserves_identity_routes_gates_and_persists(self):
        item = self.create(crew=[{"name": "CRIMSON", "specialty": "Coordination", "instruction": "Prepare fictional plans."},
                                 {"name": "HOST", "specialty": "Service", "instruction": "Prepare fictional greetings."}],
                           gates=[{"owner": "CRIMSON", "need": "Review fictional item", "brief": {}}], color="#123456")
        base = f"/api/workspaces/{item['id']}"
        status, changed, _ = self.request(base + "/agents/appearance", method="POST",
                                           body={"agent": "HOST", "title": "Guest Relations", "color": "#abcdef"})
        self.assertEqual(status, 200)
        self.assertEqual(changed["crew"][1]["appearance"], {"title": "Guest Relations", "color": "#abcdef"})
        self.assertEqual(changed["crew"][1]["name"], "HOST")
        self.assertEqual(changed["crew"][1]["routing"], item["crew"][1]["routing"])
        self.assertEqual(changed["gates"], item["gates"])
        self.assertEqual(changed["drafts"], item["drafts"])
        frame = self.room(item)
        data = self.presentation(self.request(frame.path + "?" + frame.query, port=frame.port)[1])
        self.assertEqual(data["agents"], [{"agent": "CRIMSON", "title": "Head Executive", "color": "#123456"},
                                          {"agent": "HOST", "title": "Guest Relations", "color": "#abcdef"},
                                          {"agent": "LEGAL", "title": "Legal Review", "color": ""}])
        self.assertEqual(self.request(f"/packs/{item['id']}.json", port=frame.port)[1]["crew"][1]["name"], "HOST")
        status, customized, _ = self.request(base + "/agents/appearance", method="POST", body={"agent": "LEGAL", "title": "Counsel Liaison"})
        self.assertEqual(status, 200)
        themed = self.presentation(self.request(frame.path + "?" + frame.query, port=frame.port)[1])
        self.assertEqual(next(a for a in themed["agents"] if a["agent"] == "LEGAL")["title"], "Counsel Liaison")
        self.assertEqual(next(a for a in customized["crew"] if a["name"] == "LEGAL")["name"], "LEGAL")
        status, reset, _ = self.request(base + "/agents/appearance", method="POST", body={"agent": "HOST"})
        self.assertEqual(status, 200)
        self.assertEqual(reset["crew"][1]["appearance"], {"title": "", "color": ""})
        for fields in ({"color": "red"}, {"color": "#12345678"}, {"title": "x" * 61}, {"title": "Line\nBreak"}, {"title": 4}):
            self.assertEqual(self.request(base + "/agents/appearance", method="POST", body={"agent": "HOST", **fields})[0], 400)
        self.assertEqual(self.request(base + "/agents/appearance", method="POST", body={"agent": "OTHER"})[0], 404)
        with server.Store(Path(self.sandbox.name) / "storage").connection() as db:
            self.assertEqual(self.httpd.store.get(db, item["id"])["crew"][1]["appearance"], {"title": "", "color": ""})

    def test_presentation_is_escaped_json_and_excludes_private_fields(self):
        malicious = '</script><script>window.bad=1</script>&<img src=x onerror=alert(1)>'
        item = self.create(name=malicious)
        base = f"/api/workspaces/{item['id']}"
        # The title fits its own field cap and must remain harmless literal text.
        title = '</script><img src=x onerror=alert(1)>'
        self.assertEqual(self.request(base + "/agents/appearance", method="POST", body={"agent": "CRIMSON", "title": title})[0], 200)
        with self.httpd.store.connection(write=True) as db:
            stored = self.httpd.store.get(db, item["id"])
            stored["logo"] = "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="
            stored["drafts"] = [{"text": "private drafting fixture"}]
            stored["crew"][0]["routing"] = {"provider": "secret-routing-fixture", "model": "secret-model-fixture"}
            self.httpd.store.save(db, stored)
        frame = self.room(item)
        raw = self.request(frame.path + "?" + frame.query, port=frame.port)[1]
        data = self.presentation(raw)
        self.assertEqual(set(data), {"name", "color", "logo", "agents", "studioOrigin"})
        self.assertEqual(data["studioOrigin"], f"http://127.0.0.1:{self.httpd.server_port}")
        self.assertEqual(data["name"], malicious)
        self.assertEqual(data["agents"][0]["title"], title)
        self.assertEqual(data["logo"], "")
        self.assertNotIn(malicious.encode(), raw)
        self.assertNotIn(title.encode(), raw)
        self.assertNotIn(b"secret-routing-fixture", raw)
        self.assertNotIn(b"private drafting fixture", raw)
        self.assertEqual(self.source.read_bytes(), self.html)

    def test_disabled_room_returns_null_and_does_not_allow_frames(self):
        disabled = server.create_server(0, Path(self.sandbox.name) / "disabled")
        thread = threading.Thread(target=disabled.serve_forever, daemon=True)
        thread.start()
        try:
            status, item, _ = self.request("/api/workspaces", port=disabled.server_port, method="POST",
                                           body={"name": "Local", "crew": [], "gates": []})
            self.assertEqual(status, 201)
            status, data, headers = self.request(f"/api/workspaces/{item['id']}/room", port=disabled.server_port)
            self.assertEqual((status, data), (200, {"url": None}))
            self.assertNotIn("frame-src http", headers["Content-Security-Policy"])
        finally:
            disabled.shutdown()
            disabled.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
