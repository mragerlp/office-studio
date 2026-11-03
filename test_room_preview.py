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
        self.assertIn(f"script-src 'unsafe-inline' http://127.0.0.1:{frame.port}/assets/three-r128.min.js", policy)
        self.assertNotIn("cdnjs", policy)
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

    def test_custom_roster_uses_renderer_keys_without_changing_saved_names(self):
        for name in ("OWNER", "Crimson", "CRIMSON-LONG-NAME"):
            item = self.create(crew=[{"name": name, "specialty": "Coordination", "instruction": "Prepare fictional plans."}])
            frame = self.room(item)
            self.assertIsNotNone(frame)
            exported = self.request(f"/packs/{item['id']}.json", port=frame.port)[1]
            self.assertEqual(exported["crew"][0]["name"], "CRIMSON")
            rendered = self.presentation(self.request(frame.path + "?" + frame.query, port=frame.port)[1])
            self.assertEqual(rendered["agents"][0]["title"], "Head Executive")
            self.assertTrue(rendered["agents"][0]["executive"])
            saved = self.request(f"/api/workspaces/{item['id']}")[1]
            self.assertEqual(saved["crew"][0]["name"], name)

    def test_renderer_alias_collisions_unicode_titles_and_gate_ownership(self):
        names = ["Owner", "CRIMSON", "A B", "A-B", "DESK04", "International specialist name", "\u7814\u7a76", "legal"]
        item = self.create(crew=[{"name": n, "specialty": "Synthetic lane", "instruction": "Prepare a fictional brief."} for n in names],
                           gates=[{"owner": n, "need": "Review fictional work", "brief": {}} for n in names])
        frame = self.room(item)
        pack = self.request(f"/packs/{item['id']}.json", port=frame.port)[1]
        keys = [a["name"] for a in pack["crew"]]
        self.assertEqual(len(keys), len(names))
        self.assertTrue(all(re.fullmatch(r"[A-Z][A-Z0-9 -]{0,13}", n) for n in keys))
        self.assertEqual(len(set(re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-") for n in keys)), len(keys))
        self.assertEqual([g["owner"] for g in pack["gates"]], keys)
        data = self.presentation(self.request(frame.path + "?" + frame.query, port=frame.port)[1])
        self.assertEqual([a["agent"] for a in data["agents"]], keys)
        self.assertEqual([a["title"] for a in data["agents"]], ["Owner", "Head Executive", *names[2:-1], "Legal Review"])
        self.assertEqual([a["name"] for a in self.request(f"/api/workspaces/{item['id']}")[1]["crew"]], names)

    def test_default_bundled_room_and_local_pinned_dependency(self):
        from hashlib import sha256
        app = server.create_server(0, Path(self.sandbox.name) / "bundled")
        worker = threading.Thread(target=app.serve_forever, daemon=True)
        worker.start()
        try:
            status, item, _ = self.request("/api/workspaces", port=app.server_port, method="POST",
                                            body={"name": "Bundled Synthetic Office", "crew": [], "gates": []})
            self.assertEqual(status, 201)
            response = self.request(f"/api/workspaces/{item['id']}/room", port=app.server_port)[1]
            frame = urlsplit(response["url"])
            status, page, headers = self.request(frame.path + "?" + frame.query, port=frame.port)
            self.assertEqual(status, 200)
            self.assertIn(b'async function loadPracticePack(key)', page)
            for mode in ("light", "dark"):
                status, themed, _ = self.request(f"{frame.path}?{frame.query}&appearance={mode}", port=frame.port)
                self.assertEqual(status, 200)
                self.assertIn(f'<html data-appearance="{mode}">'.encode(), themed.split(b"<head>", 1)[0])
            self.assertIn(b'src="/assets/three-r128.min.js"', page)
            self.assertNotIn(b'src="https://cdnjs', page)
            self.assertNotIn("https:", headers["Content-Security-Policy"])
            status, js, _ = self.request("/assets/three-r128.min.js", port=frame.port)
            self.assertEqual(status, 200)
            self.assertEqual(sha256(js).hexdigest(), "9274bbcec8d96168626c732b5d31c775aa8cfb7eaa0599bec0c175908a2c1ce2")
            for path in ("/assets/three-LICENSE.txt", "/assets/three-r128.min.js?x=1", "/room/office.html"):
                self.assertEqual(self.request(path, port=frame.port)[0], 404)
            self.assertNotIn(b"followupboss.com", page)
            self.assertNotIn(b"Jared", page)
            self.assertNotIn(b"studio.local", page)
            self.assertNotIn(b"local-office-bridge-example", page)
            self.assertNotIn(b"MCP plugin installed", page)
            self.assertNotIn(b"const snippet =", page)
            self.assertIn(b"Use Add agent in Office Studio", page)
            self.assertNotIn(b"Waiting for the Studio", page)
            self.assertNotIn(b"Worked out from Phone system activity in Epic", page)
            self.assertIn(b"No external feed connected", page)
            # Brand text is allowed in static HTML and escaped JSON only. It
            # must never enter the native mirror's JavaScript template literal.
            unsafe_name = "`${window.brandInjection=1}<img src=x>"
            with app.store.connection(write=True) as db:
                saved = app.store.get(db, item["id"])
                saved["name"] = unsafe_name
                app.store.save(db, saved)
            _, unsafe_page, _ = self.request(frame.path + "?" + frame.query, port=frame.port)
            native_script = unsafe_page.split(b"<script", 1)[1].split(b'<script type="application/json" id="office-studio-presentation">', 1)[0]
            self.assertNotIn(b"window.brandInjection", native_script)
            self.assertIn(b'<span class="wordmark">BEYDER<i>&amp;</i>CO.</span>', native_script)
            from build_runner import smoke_room
            smoke_room(app.server_port)
        finally:
            app.shutdown()
            app.server_close()
            worker.join(timeout=5)

    def test_one_executive_uses_saved_identity_with_custom_title_preserved(self):
        for crew, expected in (([{"name": "OWNER", "specialty": "Chief of Staff"}, {"name": "HOST", "specialty": "Service"}], 0),
                               ([{"name": "HOST", "specialty": "Service"}, {"name": "LEAD", "specialty": "Chief of Staff"}], 1),
                               ([{"name": "LEAD", "specialty": "Chief of Staff"}, {"name": "CRIMSON", "specialty": "Coordination"}], 1)):
            item = self.create(crew=[{**a, "instruction": "Prepare fictional work."} for a in crew], color="#123456")
            self.request(f"/api/workspaces/{item['id']}/agents/appearance", method="POST",
                         body={"agent": crew[expected]["name"], "title": "Company Director"})
            frame = self.room(item)
            people = self.presentation(self.request(frame.path + "?" + frame.query, port=frame.port)[1])["agents"]
            self.assertEqual([i for i, a in enumerate(people) if a["executive"]], [expected])
            self.assertEqual(people[expected]["title"], "Company Director")
            self.assertEqual(people[expected]["color"], "#123456")

    def test_public_package_contains_builtin_room_and_local_dependency(self):
        from zipfile import ZipFile
        import package
        output = package.build_package(Path(self.sandbox.name) / "public.zip")
        with ZipFile(output) as bundle:
            self.assertEqual(bundle.read("office-studio/room/office.html"), (server.ROOT / "room" / "office.html").read_bytes())
            self.assertEqual(bundle.read("office-studio/assets/three-r128.min.js"), (server.ROOT / "assets" / "three-r128.min.js").read_bytes())
            self.assertIn("office-studio/assets/three-LICENSE.txt", bundle.namelist())
            self.assertNotIn("office-studio/private-room.html", bundle.namelist())

    def test_routes_queries_hosts_and_workspace_boundaries_fail_closed(self):
        item = self.create()
        frame = self.room(item)
        other = self.create(name="Other fictional office")
        good = frame.path + "?" + frame.query
        for path in ("/", "/server.py", "/room/index.html", "/examples/iv-therapy/index.html", "/packs/re.json",
                     good + "&bridge=ws://example.invalid", good + "&pack=" + item["id"],
                     good + "&appearance=unknown", good + "&appearance=dark&appearance=light",
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
        self.assertEqual(data["agents"], [{"agent": "CRIMSON", "title": "Head Executive", "color": "#123456", "executive": True},
                                          {"agent": "HOST", "title": "Guest Relations", "color": "#abcdef", "executive": False},
                                          {"agent": "LEGAL", "title": "Legal Review", "color": "", "executive": False}])
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

    def test_empty_legacy_roster_keeps_2d_fallback_without_inventing_desks(self):
        item = self.create()
        with self.httpd.store.connection(write=True) as db:
            saved = self.httpd.store.get(db, item["id"])
            saved["crew"] = []
            self.httpd.store.save(db, saved)
        status, data, _ = self.request(f"/api/workspaces/{item['id']}/room")
        self.assertEqual((status, data), (200, {"url": None}))
        self.assertEqual(self.request(f"/api/workspaces/{item['id']}")[1]["crew"], [])


if __name__ == "__main__":
    unittest.main()
