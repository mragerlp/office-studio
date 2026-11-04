"""Native bundle smoke check. Pass the built .app path, using only disposable storage."""
import http.client
import os
from pathlib import Path
import signal
import select
import socket
import subprocess
import sys
import tempfile
import time
import unittest

APP = Path(sys.argv.pop()).resolve() if sys.argv[-1].endswith(".app") else None


class NativeAppTest(unittest.TestCase):
    def test_bundle_starts_and_stops_its_own_office(self):
        self.assertIsNotNone(APP, "Pass the built Office Studio.app")
        self.assertTrue((APP / "Contents/Helpers/office-studio-runner").is_file())
        # A busy preferred port must never cause us to open an unrelated service.
        with tempfile.TemporaryDirectory(prefix="Office Studio Native ") as folder, socket.socket() as busy:
            busy.bind(("127.0.0.1", 8765))
            busy.listen()
            process = subprocess.Popen([str(APP / "Contents/MacOS/OfficeStudio"),
                                        "--data-dir", folder, "--no-browser"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                database = Path(folder) / "office.sqlite3"
                deadline = time.monotonic() + 30
                output = b""
                while time.monotonic() < deadline and b"Office Studio: http://" not in output and process.poll() is None:
                    if select.select([process.stdout], [], [], .1)[0]:
                        output += os.read(process.stdout.fileno(), 4096)
                self.assertIsNone(process.poll(), "Native app exited before opening the server")
                self.assertIn(b"Office Studio: http://", output)
                port = int(output.decode().split("Office Studio: ")[1].splitlines()[0].strip().rsplit(":", 1)[1].rstrip("/"))
                self.assertNotEqual(port, 8765)
                self.assertTrue(database.is_file())
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
                connection.request("GET", "/api/workspaces")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b'{"workspaces": []}')
                connection.close()
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=15)
                self.assertEqual(process.returncode, 0)
                with socket.socket() as probe:
                    self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0,
                                        "Quitting left the office server running")
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGKILL)
                    process.wait(timeout=5)
                process.stdout.close()
                process.stderr.close()


if __name__ == "__main__":
    unittest.main()
