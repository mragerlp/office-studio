# Contributor instructions

Read this file and [README.md](README.md) before making changes. [help.html](help.html) describes the product workflow. Keep shared contributor rules here; vendor handoff files link back to this document.

## Start from develop

For a new checkout:

```sh
git clone --branch develop https://github.com/mragerlp/office-studio.git
cd office-studio
```

For an existing checkout, inspect the current branch and working tree first. Preserve other contributors' work. Refresh a clean `develop` with `git fetch origin` and `git pull --ff-only origin develop`, then create a focused feature branch. Use a separate checkout when necessary; do not reset or overwrite someone else's edits.

Open feature pull requests into `develop`. A release is a separate, reviewed promotion from `develop` to `main`. Merge, publication, deployment, and private handoff actions need the owner's explicit request; a code-editing task does not imply them.

## Run and orient

Source requires Python 3.10+ and a browser, with no Python package installation or frontend build.

| Task | Windows PowerShell | macOS Terminal |
| --- | --- | --- |
| Launch | `py -3 -B launch.py` | `python3 -B launch.py` |
| All tests | `py -3 -B -m unittest -v` | `python3 -B -m unittest -v` |
| Public source ZIP | `py -3 -B package.py` | `python3 -B package.py` |

The launcher prints its actual loopback address. For isolated development, pass `--data-dir` with a temporary folder; do not test against an operator's saved offices. Stop the server and clean up test processes and temporary files afterward.

| Area | Files |
| --- | --- |
| Interface and synthetic starter crews | `index.html`, `app.js`, `style.css`, `packs/` |
| Local HTTP, validation, and SQLite storage | `server.py`, `loopback_server.py` |
| Provider adapters and terminal configuration | `providers.py`, `configure_providers.py` |
| Optional private room bridge and presentation | `room_preview.py`, `room_theme.js` |
| Launching and packaging | `launch.py`, platform launchers, `package.py`, `build_runner.py` |
| Repeatable checks | `test_*.py`, `.github/workflows/` |

## Implement and verify

- Keep changes focused and follow the existing standard-library/vanilla-JavaScript architecture. Render untrusted strings with safe DOM APIs. Preserve loopback, origin, size, and route-validation boundaries.
- Keep stable agent names and IDs separate from display titles and colors. Preserve workspace isolation, stale-response protection, saved provider/model routes, and explicit demo overrides. An unavailable route must not select a different paid provider silently.
- New offices reserve a seat for Legal Review within the ten-desk cap. Keep the original intake exports intact, and preserve already-saved offices when changing a new-office default.
- For a provider addition, check its official API documentation, extend the adapter and host configuration, and test request/response parsing, model allowlists, failure handling, and recorded provider/model values with synthetic mocked responses. Expose configuration status separately from verified account access.
- Update relevant tests and user help for behavioral changes. Run focused checks while developing, then the full suite before handoff. If Node is available, also run `node --check app.js` and `node --check room_theme.js`; Node is not an application runtime requirement.
- Routine tests use no API keys and make no live model calls. Do not run installers, enable credentials, or spend provider credits merely to verify a patch. A live test must be explicitly requested and its limited result described accurately.
- Verify changed UI in a real browser with synthetic data, including a narrow viewport. Record the browser, viewport, operating system, and what was actually exercised. A syntax/unit check is not visual proof; a screenshot is not interaction proof; headless or emulated checks are not native-platform acceptance.
- Report the final behavior, files changed, checks performed, and unresolved limitations. Do not describe an unrun check as passed.

## Protect private material

Use fictional business information in fixtures, screenshots, documentation, and public packages. Do not commit credentials, environment files, local databases, customer records, uploaded tenant logos, private manuals, or owner-supplied room artwork. Do not inspect unrelated credentials or agent session histories.

The optional room source belongs to its owner and stays separate from public source. Read it only within the owner's stated task. Public packaging uses the explicit allowlist. Use `--private-room` for an explicitly requested private handoff, and keep that ZIP out of Git and public workflow artifacts. The owner cleared the README interior screenshot for public display. Obtain separate clearance before publishing additional private room images.

## Repository guidance versus application prompts

These Markdown files guide repository contributors. They do not configure an Office Studio desk or automatically become model prompts. Runtime agent instructions, workspace rules, and provider routes are application data. The drafting path sends the selected brief, agent instructions, and workspace rules; do not add repository instructions or fetch a linked operating manual into that payload implicitly.
