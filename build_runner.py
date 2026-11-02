"""Build and smoke-test native runners in CI; never bundle private room HTML."""
import argparse
import http.client
import json
import os
from pathlib import Path
import platform
import queue
import re
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
from zipfile import ZipFile

import package


ROOT = Path(__file__).resolve().parent
TARGETS = {"macos-arm64": ("Darwin", {"arm64", "aarch64"}), "windows-x64": ("Windows", {"amd64", "x86_64"})}


def check_platform(target):
    system, architectures = TARGETS[target]
    if platform.system() != system or platform.machine().lower() not in architectures:
        raise RuntimeError("The runner must be built and tested natively on its named platform and architecture.")


def check_binary(path, target):
    with path.open("rb") as stream:
        header = stream.read(64)
        if target == "windows-x64":
            if len(header) != 64 or header[:2] != b"MZ":
                raise RuntimeError("Expected an x64 Windows runner.")
            stream.seek(struct.unpack_from("<I", header, 60)[0])
            image = stream.read(6)
            if image[:4] != b"PE\0\0" or image[4:6] != b"\x64\x86":
                raise RuntimeError("Expected an x64 Windows runner.")
        elif len(header) < 8 or header[:4] != b"\xcf\xfa\xed\xfe" or struct.unpack_from("<I", header, 4)[0] != 0x0100000C:
            raise RuntimeError("Expected an arm64 macOS runner.")


def build(target, output):
    check_platform(target)
    # Keep the data allowlist separate from the broader source handoff list.
    assets = ["index.html", "help.html", "app.js", "style.css", "room_theme.js", "assets/ampersand.svg", *(f"packs/{key}.json" for key in ("re", "law", "acct", "fin", "med"))]
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="office-freeze-") as scratch:
        command = [sys.executable, "-B", "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--console",
                   "--name", "office-studio-runner", "--distpath", str(output), "--workpath", str(Path(scratch) / "work"),
                   "--specpath", scratch, "--hidden-import", "providers", "--hidden-import", "configure_providers",
                   "--hidden-import", "room_preview"]
        if target == "macos-arm64":
            command.extend(["--target-arch", "arm64"])
        for name in assets:
            command.extend(["--add-data", f"{ROOT / name}:{Path(name).parent.as_posix()}"])
        command.append(str(ROOT / "launch.py"))
        subprocess.run(command, cwd=ROOT, check=True)
    runner = output / ("office-studio-runner.exe" if target == "windows-x64" else "office-studio-runner")
    check_binary(runner, target)
    return runner


def get(port, path):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def stop(process):
    if os.name == "nt":
        # The one-file bootloader has a child: stop the entire owned process tree.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def smoke(target, archive):
    check_platform(target)
    executable = "office-studio-runner.exe" if target == "windows-x64" else "office-studio-runner"
    with tempfile.TemporaryDirectory(prefix="office-frozen-smoke-") as scratch:
        extracted = Path(scratch) / "extracted"
        with ZipFile(archive) as bundle:
            expected = {"office-studio/" + name for name in package.FILES} | {"office-studio/" + executable}
            if set(bundle.namelist()) != expected or len(bundle.namelist()) != len(expected):
                raise RuntimeError("Public native ZIP must contain only the source allowlist and one runner, with no private room.")
            for entry in bundle.infolist():
                native = entry.filename == "office-studio/office-studio-runner"
                mode = 0o755 if entry.filename.endswith(".command") or native else 0o644
                if entry.create_system != 3 or stat.S_IMODE(entry.external_attr >> 16) != mode:
                    raise RuntimeError("ZIP executable permissions were not preserved.")
            bundle.extractall(extracted)
            if os.name != "nt":
                for entry in bundle.infolist():
                    (extracted / entry.filename).chmod(stat.S_IMODE(entry.external_attr >> 16))
        app = extracted / "office-studio"
        runner = app / executable
        check_binary(runner, target)
        # No API secrets, models, private room selectors, or inherited proxies.
        environment = {name: os.environ[name] for name in
                       ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP", "USERPROFILE", "HOME", "LANG", "LC_ALL") if name in os.environ}
        options = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen([str(runner), "--no-browser", "--port", "0", "--data-dir", str(Path(scratch) / "storage")],
                                   cwd=app, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", **options)
        output = queue.Queue()
        def read_output():
            for line in process.stdout:
                output.put(line)
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            port, deadline = None, time.monotonic() + 45
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    line = output.get(timeout=0.2)
                except queue.Empty:
                    continue
                found = re.fullmatch(r"Office Studio: http://127\.0\.0\.1:(\d+)/\s*", line)
                if found:
                    port = int(found[1])
                    break
            if port is None:
                raise RuntimeError("Frozen runner did not start its own loopback office.")
            status, html = get(port, "/")
            if status != 200 or b"Office Studio" not in html:
                raise RuntimeError("Frozen runner could not serve its bundled interface.")
            status, raw = get(port, "/api/providers")
            sources = json.loads(raw)["providers"]
            if status != 200 or {p["id"] for p in sources} != {"demo", "openai", "anthropic", "gemini", "meta"}:
                raise RuntimeError("Frozen runner did not include all provider adapters.")
            if any(p["configured"] != (p["id"] == "demo") or p["models"] for p in sources):
                raise RuntimeError("Smoke test unexpectedly inherited provider configuration.")
            if get(port, "/api/workspaces") != (200, b'{"workspaces": []}'):
                raise RuntimeError("Smoke test did not start with isolated storage.")
            print(f"PASS: extracted frozen {target} runner, bundled UI, private-free ZIP and unconfigured provider list.")
        finally:
            stop(process)
            reader.join(timeout=5)
            process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "smoke"))
    parser.add_argument("--target", required=True, choices=TARGETS)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "native")
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        print(build(args.target, args.output))
    elif args.archive is None:
        parser.error("smoke requires --archive")
    else:
        smoke(args.target, args.archive)


if __name__ == "__main__":
    main()
