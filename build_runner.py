"""Build and smoke-test native runners in CI; never bundle private room HTML."""
import argparse
import http.client
import hashlib
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
from urllib.parse import urlsplit
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


def build(target, output, signing_identity=None):
    check_platform(target)
    # Keep the data allowlist separate from the broader source handoff list.
    assets = ["index.html", "help.html", "app.js", "appearance.js", "style.css", "room_theme.js", "room/office.html", "assets/three-r128.min.js", "assets/three-LICENSE.txt", "assets/ampersand.svg", *(f"packs/{key}.json" for key in ("re", "law", "acct", "fin", "med"))]
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="office-freeze-") as scratch:
        command = [sys.executable, "-B", "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--console",
                   "--name", "office-studio-runner", "--distpath", str(output), "--workpath", str(Path(scratch) / "work"),
                   "--specpath", scratch, "--hidden-import", "providers", "--hidden-import", "configure_providers",
                   "--hidden-import", "room_preview"]
        if target == "macos-arm64":
            command.extend(["--target-arch", "arm64"])
            if signing_identity:
                command.extend(["--codesign-identity", signing_identity])
        for name in assets:
            command.extend(["--add-data", f"{ROOT / name}:{Path(name).parent.as_posix()}"])
        command.append(str(ROOT / "launch.py"))
        subprocess.run(command, cwd=ROOT, check=True)
    runner = output / ("office-studio-runner.exe" if target == "windows-x64" else "office-studio-runner")
    check_binary(runner, target)
    return runner


def request(port, path, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        encoded = None if body is None else json.dumps(body)
        connection.request("GET" if body is None else "POST", path, encoded,
                           {} if body is None else {"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def get(port, path):
    return request(port, path)


def smoke_room(port, asset_root=ROOT):
    """Exercise actual bundled room assets in the extracted frozen process."""
    status, raw = request(port, "/api/workspaces", {
        "name": "Fictional Native Smoke Office", "color": "#123456",
        "crew": [{"name": "Executive fixture", "specialty": "Chief of Staff", "instruction": "Prepare synthetic plans."},
                 {"name": "Specialist fixture with a long name", "specialty": "Research", "instruction": "Prepare synthetic research."}],
        "gates": [{"owner": "Specialist fixture with a long name", "need": "Review fictional work", "brief": {}}]})
    if status != 201:
        raise RuntimeError("Frozen runner could not save a synthetic office.")
    workspace = json.loads(raw)
    status, raw = get(port, f"/api/workspaces/{workspace['id']}/room")
    frame = urlsplit(json.loads(raw)["url"])
    if status != 200 or frame.scheme != "http" or frame.hostname != "127.0.0.1" or not frame.port or frame.port == port:
        raise RuntimeError("Frozen runner did not expose its isolated bundled room.")
    status, page = get(frame.port, frame.path + "?" + frame.query)
    if status != 200 or b'async function loadPracticePack(key)' not in page or b'src="/assets/three-r128.min.js"' not in page or b'src="https://cdnjs' in page:
        raise RuntimeError("Frozen room is missing its original scene or local dependency rewrite.")
    adapter = (asset_root / "room_theme.js").read_text(encoding="utf-8").encode()
    script = b'<script data-office-theme-adapter="1">' + adapter + b'</script>'
    if page.count(b'<script data-office-theme-adapter="1">') != 1 or script not in page:
        raise RuntimeError("Bundled room_theme.js differs from the adapter served by the runner.")
    match = re.search(rb'<script type="application/json" id="office-studio-presentation">(.*?)</script>', page, re.S)
    presentation = json.loads(match[1]) if match else {}
    if presentation.get("name") != workspace["name"] or presentation.get("agents", [{}])[0].get("title") != "Head Executive":
        raise RuntimeError("Frozen room presentation does not match the saved office.")
    status, raw = get(frame.port, f"/packs/{workspace['id']}.json")
    pack = json.loads(raw)
    if (status != 200 or len(pack["crew"]) != len(workspace["crew"]) or pack["gates"] != []
            or [rule["owner"] for rule in workspace["gates"]] != ["Specialist fixture with a long name"]):
        raise RuntimeError("Frozen room must preserve the crew and keep saved policy out of its approval queue.")
    status, javascript = get(frame.port, "/assets/three-r128.min.js")
    if status != 200 or hashlib.sha256(javascript).hexdigest() != "9274bbcec8d96168626c732b5d31c775aa8cfb7eaa0599bec0c175908a2c1ce2":
        raise RuntimeError("Frozen room did not serve its pinned local Three.js.")
    if javascript != (asset_root / "assets/three-r128.min.js").read_bytes():
        raise RuntimeError("Bundled assets/three-r128.min.js differs from the served renderer.")


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
            paths = ["index.html", "help.html", "app.js", "appearance.js", "style.css", "assets/ampersand.svg"]
            paths.extend(f"packs/{key}.json" for key in ("re", "law", "acct", "fin", "med"))
            for path in paths:
                if get(port, "/" + path) != (200, (app / path).read_bytes()):
                    raise RuntimeError(f"Bundled {path} differs from the file served by the runner.")
            status, raw = get(port, "/api/providers")
            sources = json.loads(raw)["providers"]
            if status != 200 or {p["id"] for p in sources} != {"demo", "openai", "anthropic", "gemini", "meta"}:
                raise RuntimeError("Frozen runner did not include all provider adapters.")
            if any(p["configured"] != (p["id"] == "demo") or p["models"] for p in sources):
                raise RuntimeError("Smoke test unexpectedly inherited provider configuration.")
            if get(port, "/api/workspaces") != (200, b'{"workspaces": []}'):
                raise RuntimeError("Smoke test did not start with isolated storage.")
            smoke_room(port, app)
            print(f"PASS: extracted frozen {target} runner, bundled UI and isolated local room, private-free ZIP and unconfigured provider list.")
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
    parser.add_argument("--signing-identity", help="Existing macOS signing identity for the runner and its embedded libraries")
    args = parser.parse_args()
    if args.action == "build":
        print(build(args.target, args.output, args.signing_identity))
    elif args.archive is None:
        parser.error("smoke requires --archive")
    else:
        smoke(args.target, args.archive)


if __name__ == "__main__":
    main()
