"""Build a static hosted site with the same local 3D scene as the desktop edition."""
import argparse
import base64
import html
import json
import os
import re
from pathlib import Path
from shutil import copyfile
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def public_config(url, key):
    origin = urlsplit(url)
    if (origin.scheme != "https" and not (origin.scheme == "http" and origin.hostname in ("localhost", "127.0.0.1"))) or not re.fullmatch(r"[a-zA-Z0-9.-]+(:[0-9]{1,5})?",origin.netloc) or origin.query or origin.fragment or origin.path not in ("", "/"):
        raise ValueError("Set SUPABASE_URL to your project origin.")
    if not key.startswith("sb_publishable_"):
        try:
            payload = key.split(".")[1]
            role = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["role"]
        except (IndexError, ValueError, KeyError, UnicodeError) as exc:
            raise ValueError("Set SUPABASE_PUBLISHABLE_KEY to a publishable key or legacy anon key.") from exc
        if role != "anon":
            raise ValueError("Only a public anon key may be included in the site.")
    return {"url":url.rstrip("/"), "publishableKey":key}


def replace_once(source, marker, replacement):
    if source.count(marker) != 1:
        raise ValueError("The bundled room template changed at " + marker[:55])
    return source.replace(marker, replacement, 1)


def build_room():
    page = (ROOT / "room/office.html").read_text(encoding="utf-8")
    three = (ROOT / "assets/three-r128.min.js").read_text(encoding="utf-8")
    bootstrap = (HERE / "room-client.js").read_text(encoding="utf-8")
    theme = (ROOT / "room_theme.js").read_text(encoding="utf-8")
    # CSP denies network, forms, and subframes even if the renderer gains a new link.
    policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; base-uri 'none'; form-action 'none'"
    page = replace_once(page, "<head>", '<head><meta http-equiv="Content-Security-Policy" content="' + policy + '">')
    tag = '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>'
    page = replace_once(page, tag, "<script>" + bootstrap + "</script><script>" + three + "</script>")
    page = replace_once(page, "boot().catch(err => {", "boot().then(() => OfficeStudioHostedRoom.mounted()).catch(err => {")
    page = replace_once(page, "</body>", "<script>OfficeStudioHostedRoom.pack.then(() => {" + theme + "});</script></body>")
    # All saved work is changed in the authenticated host. The room mirrors desk status.
    page = replace_once(page, "</head>", "<style>#pCompose,.p-compose{display:none!important}</style></head>")
    return page


def build(output, config):
    if output.resolve() in (ROOT, HERE):
        raise ValueError("Choose a separate output directory.")
    output.mkdir(parents=True, exist_ok=True)
    expected = {"index.html", "style.css", "auth.js", "app.js", "room-view.js", "appearance.js",
                "ampersand.svg", "config.js", "suite-room.html", "three-LICENSE.txt", "OFL-Old-Standard.txt"}
    if any(path.name not in expected or not path.is_file() or path.is_symlink() for path in output.iterdir()):
        raise ValueError("Use an empty directory or an earlier Office Studio hosted build.")
    policy = ("default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' "
              + config["url"] + "; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'")
    page = (HERE / "index.html").read_text(encoding="utf-8")
    page = replace_once(page,"<head>",'<head><meta http-equiv="Content-Security-Policy" content="' + html.escape(policy) + '">')
    (output / "index.html").write_text(page,encoding="utf-8")
    for name in ("style.css","auth.js","app.js","room-view.js"):
        copyfile(HERE / name,output / name)
    copyfile(ROOT / "appearance.js", output / "appearance.js")
    copyfile(ROOT / "assets/ampersand.svg", output / "ampersand.svg")
    copyfile(ROOT / "assets/OFL-Old-Standard.txt", output / "OFL-Old-Standard.txt")
    (output / "config.js").write_text("window.OFFICE_STUDIO_CONFIG = " + json.dumps(config) + ";\n",encoding="utf-8")
    (output / "suite-room.html").write_text(build_room(),encoding="utf-8")
    copyfile(ROOT / "assets/three-LICENSE.txt",output / "three-LICENSE.txt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/hosted")
    args = parser.parse_args()
    build(args.output, public_config(os.environ.get("SUPABASE_URL",""), os.environ.get("SUPABASE_PUBLISHABLE_KEY","")))
