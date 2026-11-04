"""Distribution validation before executing a packaged native runner."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import build_runner
import package


class PackageValidationTests(unittest.TestCase):
    def test_native_smoke_accepts_executable_mac_build_scripts(self):
        # Validate the real allowlisted package, stopping at the binary boundary.
        # Regression: smoke used to reject the new Mac scripts' required 0755 mode.
        with tempfile.TemporaryDirectory() as folder:
            runner = Path(folder) / "office-studio-runner.exe"
            runner.write_bytes(b"synthetic runner: never executed")
            archive = package.build_package(Path(folder) / "candidate.zip", runner=runner)
            with ZipFile(archive) as bundle:
                for name in ("macos/build-runner.sh", "script/build_and_run.sh"):
                    self.assertEqual((bundle.getinfo("office-studio/" + name).external_attr >> 16) & 0o777, 0o755)
            with patch.object(build_runner, "check_platform"), patch.object(
                    build_runner, "check_binary", side_effect=RuntimeError("binary boundary reached")):
                with self.assertRaisesRegex(RuntimeError, "^binary boundary reached$"):
                    build_runner.smoke("windows-x64", archive)


if __name__ == "__main__":
    unittest.main()
