"""Build an allowlisted source or native-runner ZIP; private HTML is opt-in."""
import argparse
from pathlib import Path
import stat
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent
FILES = (
    "README.md", "index.html", "help.html", "style.css", "app.js", "server.py", "providers.py",
    "package.py", "test_office.py", "test_providers.py", ".gitignore",
    "launch.py", "configure_providers.py", "loopback_server.py", "room_preview.py", "room_theme.js", "build_runner.py",
    "Start Office Studio.cmd", "Start Office Studio.command", "Configure Providers.cmd", "Configure Providers.command",
    "test_launcher.py", "test_room_preview.py", "test_room_alert.py", "test_setup.py",
    "docs/setup.png", "docs/office-interior.png", "docs/boardroom.png",
    "assets/ampersand.svg", "assets/OFL-Old-Standard.txt",
    "room/office.html", "assets/three-r128.min.js", "assets/three-LICENSE.txt",
    "AGENTS.md", "MUSE.md", "GEMINI.md", "CLAUDE.md", "CODEX.md",
    "packs/re.json", "packs/law.json", "packs/acct.json", "packs/fin.json", "packs/med.json",
)


def add_file(bundle, source, name, *, executable=False):
    """Record Unix permissions explicitly even when packaging on Windows."""
    entry = ZipInfo("office-studio/" + name)
    entry.create_system = 3
    entry.compress_type = ZIP_DEFLATED
    entry.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
    bundle.writestr(entry, source.read_bytes())


def build_package(output=None, runner=None, private_room=None):
    output = Path(output) if output is not None else ROOT / "dist" / "office-studio.zip"
    sources = [(ROOT / name, name, name.endswith(".command")) for name in FILES]
    if runner is not None:
        runner = Path(runner)
        windows = runner.suffix.lower() == ".exe"
        sources.append((runner, "office-studio-runner.exe" if windows else "office-studio-runner", not windows))
    if private_room is not None:
        private_room = Path(private_room).expanduser()
        if private_room.suffix.lower() not in (".html", ".htm"):
            raise ValueError("--private-room must explicitly name a local HTML file.")
        sources.append((private_room, "private-room.html", False))
    # Fail before replacing a previous package if any required input is absent.
    if any(not source.is_file() for source, _, _ in sources):
        raise ValueError("A required distribution file or explicit input is missing.")
    if any(source.resolve() == output.resolve() for source, _, _ in sources):
        raise ValueError("The output must differ from every package input.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=output.parent, delete=False) as scratch:
        pending = Path(scratch.name)
    try:
        with ZipFile(pending, "w", compression=ZIP_DEFLATED) as bundle:
            for source, name, executable in sources:
                add_file(bundle, source, name, executable=executable)
        pending.replace(output)
    finally:
        pending.unlink(missing_ok=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, help="Native one-file runner to place beside the launchers")
    parser.add_argument("--output", type=Path, help="Output ZIP (default: dist/office-studio.zip)")
    parser.add_argument("--private-room", type=Path, help="PRIVATE LOCAL HANDOFF ONLY: explicitly include this HTML as private-room.html")
    args = parser.parse_args()
    try:
        result = build_package(args.output, args.runner, args.private_room)
    except (OSError, ValueError):
        parser.error("Could not package the explicit inputs. Check that required files exist and the output is writable.")
    print(result)
    if args.private_room:
        print("Private room included. Keep this handoff private; do not upload it as a public build artifact.")


if __name__ == "__main__":
    main()
