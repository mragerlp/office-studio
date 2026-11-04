# Office Studio in Xcode

Read [the current handoff state](../docs/CURRENT-STATE.md) first and verify the review branch and source pin. The native target is **Apple Silicon arm64, macOS 13 minimum**. Reconciled Mac delivery remains **HOLD** pending an exact-source rebuild, physical workflow acceptance, authorized Release signing/notarization/stapling, and the exact ZIP's browser-download, extraction and Finder first-launch checks. Earlier Mac previews and Windows tests do not establish those results.

Open OfficeStudio.xcodeproj, choose the shared **OfficeStudio** scheme, and Run.
The Debug target builds an Apple Silicon app using the existing local server and interface.
The app opens your browser, keeps its server running while open, and stops the server when you Quit.
Your existing offices remain in ~/.office-studio. Closing a browser tab leaves the native app running.
Reopening the app reopens its current office address.

The Xcode build embeds a fresh frozen runner into Office Studio.app/Contents/Helpers.
It requires Python 3.10+ with the repository's pinned PyInstaller 6.22.3 available to that interpreter.
Set OFFICE_STUDIO_PYTHON to its absolute Python path in Local.xcconfig beside this file.
Local.xcconfig is private machine configuration and ignored by Git.
The project has no frontend compilation or third-party Swift dependencies.

From the source checkout, ./script/build_and_run.sh builds and opens the app.
./script/build_and_run.sh --verify builds it and tests disposable storage,
port collision fallback, HTTP readiness, and server cleanup on native app termination.

You can also pass --data-dir /absolute/test/folder or --no-browser to the app
using Xcode's scheme arguments or open --args. These are optional operator controls.
Routine tests must use a disposable data directory.

## Signing

Debug uses ad-hoc signing for local development. To prepare a Release archive,
select the intended bundle identifier, your authorized Developer ID Application identity,
and team in Xcode's Signing & Capabilities settings. The build passes that identity
to PyInstaller to sign the nested runner and its embedded libraries consistently.
The app target has hardened runtime enabled and sandboxing disabled for the local server.

Signed Release archiving, notarization, stapling, and downloaded Gatekeeper launch
require separate verification with the distribution identity. A successful Debug build
does not establish those results. Keep credentials and notarization profiles out of source.
