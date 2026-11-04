# Office Studio: start here for Igor and the next agent

Status recorded **4 November 2026**. This is a **packaging candidate, not a production deliverable**. The tested code baseline is `0c24b7dfe3b6bf30706fce6c1c35d91a6eae7795`. Later documentation or packaging commits have their own pins; this baseline is not a claim about the current branch HEAD or a later package's contents.

The reconciliation handoff review target is **`codex/igor-handoff-20261104`**, with a pull request intended for `develop`. Verify the review branch and its actual full commit before continuing this handoff; cloning the default `develop` alone may omit the candidate. The normal future-feature workflow remains in AGENTS. A review-branch handoff does not establish a merge or release.

## First steps

- **Igor:** read the platform table below, then use the [local walkthrough](../README.md#give-a-desk-a-file) with fictional data. A source checkout and an unsigned Windows candidate exist in the recorded handoff; a verified Mac download for this baseline remains **HOLD**. Jared retains the delivery decision.
- **Any repository agent:** read this page, [AGENTS.md](../AGENTS.md), [README.md](../README.md), and the relevant platform guide before changing files. Record the actual checkout pin and working-tree state. Preserve other contributors' work and report any difference from the tested baseline.
- **Mac agent:** start with [macos/README.md](../macos/README.md). Rebuild the exact intended source and establish physical Mac acceptance before calling a package ready for Igor. Earlier Mac previews are different revisions.
- **Hosted agent:** start with [hosted/README.md](../hosted/README.md) and the four open findings below. A mocked login or configured download link is not a deployed service or a verified account connection.

The shared rules apply to [Codex/ChatGPT](../CODEX.md), [Claude Code](../CLAUDE.md), [Gemini CLI](../GEMINI.md), and [Muse Code](../MUSE.md). Those files route contributors to the same instructions; they do not configure the app's desks.

## Vision and the working local workflow

Office Studio gives a business a spatial home for its crew: named desks, clear specialties, source-linked work and owner review. Preserve Igor's building, the Hudson river, suspension bridge, skyline and signature ampersand while improving the workflows. Department floors, voice, mailbox operations, deeper integrations and broader shared access remain planned work.

The [scaling and department-floor research](research/2026-11-03-scaling/README.md) and [source register](research/2026-11-03-scaling/sources.md) record proposed next steps checked on 3 November 2026 at an earlier baseline. Read them as dated research, not implemented capability or current account-access proof.

The implemented local path is: create an office, select a desk, attach a text file or write a brief, choose an explicit local demo or a configured provider, review the draft, approve or decline, then download an approved result. Saved work belongs to its office and stable desk identity. Every new office reserves Legal Review within the ten-desk limit. Saved pending Head Executive drafts control the executive alert; a standing rule alone does not.

For the offline rehearsal, use [examples/friday-inquiry.txt](../examples/friday-inquiry.txt), Guest Desk and **Local demo · this draft only**. Ask for the guest's preferred Friday time while leaving availability unconfirmed. To find approved work again, use **GUEST DESK → Delivered → View approved drafts**, or open the review table in **Desks & drafts**. This narrow demo fixture does not establish general model capability. Approval records a local decision; sending messages and changing business records remain separate owner actions.

The local edition uses Python 3.10+, a browser and SQLite. Source needs no Python packages or frontend build. Packaged runtimes and the native Mac wrapper are separate build outputs. Use disposable data for tests:

| Action from the repository root | Windows PowerShell | macOS Terminal |
| --- | --- | --- |
| Launch a synthetic rehearsal | `py -3 -B launch.py --data-dir "$env:TEMP/Office-Studio-Rehearsal-$([guid]::NewGuid().ToString('N'))"` | `python3 -B launch.py --data-dir "$(mktemp -d)"` |
| Python checks | `py -3 -B -m unittest -v` | `python3 -B -m unittest -v` |
| Local browser regressions | `node tests/frontend-reconciliation.cjs` | `PYTHON="$(command -v python3)" node tests/frontend-reconciliation.cjs` |
| Mocked hosted auth checks | `node --test hosted/tests/auth.test.cjs` | `node --test hosted/tests/auth.test.cjs` |

Use a fresh test directory for each rehearsal and the actual address printed by the launcher. Node browser checks additionally need an existing Playwright/Chrome installation; they are not required to run the app. Stop owned test processes and report cleanup. [Full workflow and packaging commands](../README.md#check-and-package)

## Three platforms: code, artifacts and acceptance

The `get.html` site builder has macOS download, Windows download and Chrome web app choices. Source support for those choices does not establish that a release URL or hosted deployment is available.

| Platform | Code present | Available artifact recorded at the baseline | Tested status and remaining gate |
| --- | --- | --- | --- |
| Windows x64 | Local/configured-provider launchers, frozen-runner build and hosted-site launcher. | The private unsigned candidate ZIP pinned below; the owner controls access. | Reported extracted-runner and visible local-demo checks passed. Browser-downloaded SmartScreen, physical OS file-picker and touch acceptance remain **UNVERIFIED**. This is not a general installer-release acceptance. |
| macOS | Xcode project, shared scheme, AppKit launcher, nested-runner build/signing hooks and lifecycle test; **Apple Silicon arm64, macOS 13 minimum**. | Source is present. An earlier ad-hoc-signed Mac preview is a different revision; no accepted Mac app for the reconciled baseline is recorded. | **HOLD:** rebuild this source, run native lifecycle and physical workflow tests, then verify the intended signing and exact downloaded-package path. Windows or headless tests do not establish Mac acceptance. |
| Chrome / hosted web | Static host, shared room, Supabase migration, auth client and drafting function. Local SQLite offices do not automatically sync to hosted accounts. | Source and build tooling are present; no verified public deployment or live login is established by this handoff. | Mocked auth/browser evidence only. **HOLD** for customers until the four findings and live identity, isolation, revocation, provider-grant and recovery gates are resolved. |

## Evidence and exact baseline pins

**Evidence sensor:** the owner's private reconciliation readiness report dated 4 November 2026 and its Mac continuation note. Results in this section are **previously reported for the baseline**, not new tests run while writing this page. The public document does not include the private evidence bundle, presentation assets, runtime record IDs, account details or machine paths. Ask the owner for the corresponding private evidence when needed. Fresh test results must name their own source and package pins.

| Baseline check | Previously reported result | Evidence boundary |
| --- | --- | --- |
| Full Python suite | **62/62 passed**, zero skips | Synthetic local HTTP/storage/provider regressions. |
| Local frontend reconciliation | **7/7 passed** | Guided headless Chrome with software WebGL. |
| Hosted auth unit tests | **6/6 passed**, zero skips | Mocked identity/session behavior, including local sign-out. |
| Hosted browser walkthrough | Passed; zero external requests | Mocked Google/Microsoft/Apple and opt-in ChatGPT; does not prove live OAuth, deployed RLS or provider access. |
| Windows frozen build/package/lifecycle | Reported passed | Actual unsigned executable, extracted package and owned-process cleanup; compilation reproducibility was not tested. |
| Visible Windows local walkthrough | Reported passed with input-picker limitation | Synthetic local demo, approval and download. The file was seeded via the loopback API after the browser extension blocked the picker. Physical OS picker acceptance remains unverified. |
| Independent saved-reply retrieval | Found the approved reply in **2 clicks, 10.755 seconds**, excluding setup/orientation | One fresh-agent run via **Desks & drafts → The review table**. Independent use of the desk's Delivered route is **UNVERIFIED**. The fixture was same-day, so “yesterday” was not proved. This is not customer research. |

The visible narrow-window check used Enter to activate Delivered after pointer targeting was intercepted. It does not establish mobile touch acceptance. Local incomplete-output rejection, retry protection and explicit-demo recovery do not establish the same behavior in the hosted implementation or exactly-once paid billing.

| Source identity | Exact commit |
| --- | --- |
| Tested reconciled code baseline | `0c24b7dfe3b6bf30706fce6c1c35d91a6eae7795` |
| Integration merge | `9b238f4aea1f9ccb9b0132677c9c0d6b2343289a` |
| Windows parent | `5f5481f2f56ecb696d7f7f28db0d2b2de7c98843` |
| Mac parent | `0f49d8303c9098a0c2aa67cb2c273998a70752f9` |
| Mac product-fix ancestor | `cbcf3b787fe0b3df83cf31fd817fc077fa30e965` |
| Shared ancestor | `9e9beee71b429f54f311fe8d2915ed80c965582d` |

| Earlier private Windows artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `Office-Studio-Windows-0c24b7d-candidate.zip` | 13,830,793 | `b48df56ec0d2726809b5184c7b4e6650573956a0c40cf9facc6574b62916098c` |
| Embedded Windows x64 PE runner, Authenticode **NotSigned** | 12,030,279 | `a09f2104d99d24d266dccf92af2f3455850240a0dc04897ebe815b0dc4004840` |

These hashes identify the earlier private artifacts only. A new source ZIP, repackaged handoff or rebuilt executable needs its own hash and manifest. Do not label a new package with these earlier hashes or describe an old Mac executable as the reconciled build.

## Open gates and highest-priority work

| Priority / owner | Next concrete step | Required evidence before advancing |
| --- | --- | --- |
| 1 · Mac agent + Jared | Preserve current Mac work; verify transferred inputs; build the exact intended source on an internal drive. Run native lifecycle, rendered-room and changed owner-workflow checks with disposable data. | Full source pin, build configuration, command exits and physical Mac observations. Check actual arm64/macOS/tool versions; do not reuse older preview results. |
| 2 · Jared + Mac build owner | Establish an authorized Developer ID Application identity and the intended distribution path. Earlier evidence reported no suitable identity; current availability must be checked. | Hardened runtime and nested-runner signature verification, notarization/stapling, then the exact ZIP downloaded in a browser, extracted and launched through Finder with quarantine intact. A local/ad-hoc Debug launch is insufficient. |
| 3 · Fresh Mac tester | Find the approved Friday reply without hints; test the physical file picker, keyboard and rendered Hudson scene on the exact candidate. | Separate guided workflow and independent retrieval results; record clicks, hesitation, fixture age, viewports and source/package pins. If unavailable, keep **HOLD**. |
| 4 · Hosted engineer | Reproduce and fix the four source findings below before a customer pilot. | Focused failing-then-passing regressions, followed by scoped staging evidence. Preserve ambiguous live requests rather than replaying a potentially billed call. |
| 5 · Pilot owner + identity/provider engineer | Establish live dedicated test-account OAuth, tenant isolation, account linking, grants, remote revocation, backups/recovery and bounded spending. | Separately authorized real-service tests with exact scope and no secrets in reports. Mocked tests and configured keys are not this evidence. |
| 6 · Local workflow engineer | Define safe manual reconciliation/cancellation and stale-reservation cleanup for ambiguous live attempts. | Recovery tests that preserve saved outcomes and do not silently replay paid work. Current explicit-offline-demo recovery is narrower. |

The four hosted findings remain **source-level concerns**, not claims of observed production incidents:

1. **Office/upload retries can duplicate records.** [hosted/app.js](../hosted/app.js) creates an office without a retained client request identity and assigns a fresh upload ID on each submit. Reproduce a committed response lost in transit and make the user retry safe.
2. **Refresh does not recover an orphaned preparing run.** The same file tells users to refresh, but its refresh path reads records; it does not resubmit the retained request to invoke stale-run handling. Demonstrate recovery after interruption without causing a second provider call.
3. **Remote logout revocation is not guaranteed after failure or token expiry.** [hosted/auth.js](../hosted/auth.js) clears local credentials, then attempts revocation with the saved access token. An expired token or failed request can leave remote revocation unconfirmed. Local sign-out has mocked coverage; successful remote revocation needs separate evidence.
4. **Hosted provider output lacks the local completion checks.** [supabase/functions/office-drafts/providers.js](../supabase/functions/office-drafts/providers.js) extracts text without checking the providers' completion/termination metadata. Add tests for truncated or incomplete outputs before allowing them into review; the local Python fix does not cover this adapter.

Apple, Google and Microsoft sign-in wiring is present and mocked. **ChatGPT stays hidden by default**; its opt-in path has mock coverage only and requires a supported, approved configuration plus compatibility and account-linking checks. Do not infer consumer-subscription inference/API entitlement from app login. Mailbox access, model-provider access and billing each require their own grants. No live account access, paid generation or mailbox capability is established by this handoff.

Mac downloaded/solo handoff, customer pilot and production remain **HOLD** until their own gates are met. Packaging this source does not clear those gates. Do not bypass quarantine, use another signing identity, expose private artifacts or publish/deploy merely to complete a check.

## Agent return contract

Return a concise report to the owner with:

1. Exact source commit, branch and working-tree state; changed paths and reasons; exact package names, SHA-256 values and manifest if packaging changed.
2. Actual checks, exit codes and pass/fail/skip counts. Separate fresh observations from prior reported results, and static/mocked/headless evidence from physical-platform and downloaded-package acceptance.
3. Separate verdicts for Windows local demo, Mac guided demo, independent solo handoff, downloaded distribution, customer pilot and production. Name every remaining **HOLD** or **UNVERIFIED** item and its owner/next step.
4. Any signing/quarantine findings, private-asset preservation and cleanup outcome, without credentials, tenant/account identifiers, private presentation data or operator paths in public files.

Keep public source and private delivery materials separate. Use the explicit packaging allowlist. Never create `BOARD.md`. Follow the branch and owner-authorization rules in [AGENTS.md](../AGENTS.md); a technical verdict is not permission to merge, publish, deploy or send a private handoff.
