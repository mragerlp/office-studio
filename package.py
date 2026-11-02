"""Build a portable source ZIP using an explicit list of distributable files."""
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
FILES = (
    "README.md", "index.html", "style.css", "app.js", "server.py", "providers.py",
    "package.py", "test_office.py", "test_providers.py", ".gitignore",
    "docs/boardroom.png",
    "packs/re.json", "packs/law.json", "packs/acct.json", "packs/fin.json", "packs/med.json",
)


def main():
    output = ROOT / "dist" / "office-studio.zip"
    output.parent.mkdir(exist_ok=True)
    with NamedTemporaryFile(dir=output.parent, delete=False) as scratch:
        pending = Path(scratch.name)
    try:
        with ZipFile(pending, "w", compression=ZIP_DEFLATED) as bundle:
            for name in FILES:
                bundle.write(ROOT / name, "office-studio/" + name)
        pending.replace(output)
    finally:
        pending.unlink(missing_ok=True)
    print(output)


if __name__ == "__main__":
    main()
