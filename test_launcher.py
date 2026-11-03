"""Local-only launcher checks: python -B -m unittest -v test_launcher.py."""
import errno
import io
import os
from http.server import BaseHTTPRequestHandler
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

import launch
from loopback_server import LoopbackHTTPServer


class ReadyHandler(BaseHTTPRequestHandler):
    requests = 0

    def do_GET(self):
        type(self).requests += 1
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args):
        pass


class LauncherTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows double-click wrapper")
    def test_windows_wrapper_finds_python_in_a_folder_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="Office Studio launcher ") as temporary:
            folder = Path(temporary)
            for name in ("launch.py", "Start Office Studio.cmd"):
                shutil.copyfile(launch.ROOT / name, folder / name)
            # Supply the known interpreter as a PATH fixture; never inspect keys.
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            environment = {"PATH": str(Path(sys.executable).parent), "SystemRoot": system_root,
                           "COMSPEC": str(Path(system_root) / "System32" / "cmd.exe"), "TEMP": temporary, "TMP": temporary,
                           "USERPROFILE": temporary}
            result = subprocess.run(f'"{folder / "Start Office Studio.cmd"}" --help', shell=True, cwd=folder, env=environment,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("usage: launch.py", result.stdout)

    def test_occupied_port_gets_own_socket_and_browser_opens_once_when_ready(self):
        with socket.socket() as unrelated:
            unrelated.bind(("127.0.0.1", 0))
            unrelated.listen()
            occupied = unrelated.getsockname()[1]

            def factory(*, port, data_dir, room_file):
                return LoopbackHTTPServer(("127.0.0.1", port), ReadyHandler)

            office, fallback = launch.bind_office(factory, occupied, Path("unused"), None)
            self.assertTrue(fallback)
            self.assertNotEqual(office.server_port, occupied)
            thread = threading.Thread(target=office.serve_forever, daemon=True)
            thread.start()
            try:
                ReadyHandler.requests = 0
                with patch.object(launch.webbrowser, "open", return_value=True) as browser:
                    launch.open_when_ready(office.server_port, threading.Event(), timeout=2)
                browser.assert_called_once_with(f"http://127.0.0.1:{office.server_port}/", new=2)
                self.assertEqual(ReadyHandler.requests, 1)
            finally:
                office.shutdown()
                office.server_close()
                thread.join(timeout=2)

    def test_storage_or_permission_errors_do_not_trigger_port_fallback(self):
        factory = Mock(side_effect=PermissionError(errno.EACCES, "denied"))
        with self.assertRaises(PermissionError):
            launch.bind_office(factory, 8765, Path("unused"), None)
        self.assertEqual(factory.call_count, 1)

    def test_not_ready_or_stopped_never_opens_browser(self):
        connection = Mock()
        connection.getresponse.side_effect = OSError("not serving")
        with patch.object(launch.http.client, "HTTPConnection", return_value=connection), patch.object(launch.webbrowser, "open") as browser:
            launch.open_when_ready(12345, threading.Event(), timeout=0.01)
            browser.assert_not_called()
        stopped = threading.Event()
        stopped.set()
        with patch.object(launch.webbrowser, "open") as browser:
            launch.open_when_ready(12345, stopped)
            browser.assert_not_called()

    def test_room_selection_is_explicit_and_missing_explicit_file_fails(self):
        with tempfile.TemporaryDirectory(prefix="office-launcher-test-") as temporary:
            folder = Path(temporary)
            private = folder / "private-room.html"
            selected = folder / "owner room.html"
            private.write_text("synthetic private room", encoding="utf-8")
            selected.write_text("synthetic explicit room", encoding="utf-8")
            with patch.object(launch, "ROOT", folder), patch.dict(launch.os.environ, {"OFFICE_STUDIO_ROOM_FILE": ""}):
                self.assertEqual(launch.find_room(), private.resolve())
                self.assertEqual(launch.find_room(selected), selected.resolve())
                with patch.dict(launch.os.environ, {"OFFICE_STUDIO_ROOM_FILE": "owner room.html"}):
                    self.assertEqual(launch.find_room(), selected.resolve())
                with self.assertRaises(ValueError):
                    launch.find_room("missing.html")
                private.unlink()
                self.assertEqual(launch.find_room(), folder / "room" / "office.html")

    def test_configuration_precedes_binding_and_cancellation_reveals_no_input(self):
        order = []
        office = Mock(server_port=12345)
        office.serve_forever.side_effect = KeyboardInterrupt
        configure = Mock(side_effect=lambda: order.append("configure"))
        factory = Mock(side_effect=lambda **_args: (order.append("bind"), office)[1])
        modules = {"configure_providers": types.SimpleNamespace(configure_session=configure),
                   "server": types.SimpleNamespace(create_server=factory)}
        with patch.dict("sys.modules", modules), patch.object(launch, "find_room", return_value=None), patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(launch.main(["--configure", "--no-browser"]), 0)
        self.assertEqual(order, ["configure", "bind"])
        office.server_close.assert_called_once()
        for exception in (EOFError("private input"), KeyboardInterrupt(), ValueError("private input")):
            configure.side_effect = exception
            factory.reset_mock()
            output = io.StringIO()
            with patch.dict("sys.modules", modules), patch.object(launch, "find_room", return_value=None), patch("sys.stderr", new=output):
                self.assertEqual(launch.main(["--configure", "--no-browser"]), 1)
            self.assertNotIn("private input", output.getvalue())
            factory.assert_not_called()

    def test_frozen_optional_room_is_next_to_executable_not_extraction_directory(self):
        with tempfile.TemporaryDirectory(prefix="office-launcher-frozen-") as temporary:
            folder = Path(temporary)
            private = folder / "private-room.html"
            private.write_text("synthetic private room", encoding="utf-8")
            with patch.object(launch.sys, "frozen", True, create=True), patch.object(launch.sys, "executable", str(folder / "office-studio-runner.exe")), patch.object(launch, "ROOT", folder / "extraction"), patch.dict(launch.os.environ, {"OFFICE_STUDIO_ROOM_FILE": ""}):
                self.assertEqual(launch.find_room(), private.resolve())


if __name__ == "__main__":
    unittest.main()
