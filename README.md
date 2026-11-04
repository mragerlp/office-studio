# Office Studio

**Igor and the next agent: [start with the current state and handoff](docs/CURRENT-STATE.md).** This review branch packages the reconciled candidate; Mac rebuild/download acceptance and hosted customer readiness remain **HOLD**. The page distinguishes implemented code, available artifacts and prior test evidence.

Office Studio is a local web app for your business's crew. Give the Head Executive a brief for the morning meeting, or ask a specialist to draft a client update. Each desk can use a different model. The owner reviews the draft and records a decision in the boardroom.

The original 3D office and signature ampersand come from **Beyder & Co.** When a saved draft from the Head Executive awaits your decision, the header ampersand and room sculpture turn red. Select the header mark to open the draft. Approving or declining the last pending executive draft clears both marks. The idle header glyph uses readable ink when the business accent is hard to see against the selected theme, with no background tile or glow.

[Run the local app](#start-locally) · [Try the file walkthrough](#give-a-desk-a-file) · [Set up the hosted pilot](hosted/README.md) · [Contributor guide](AGENTS.md)

## Ways to open Office Studio

The hosted site builds a `get.html` page with three choices: **macOS download**, **Windows download**, and **Chrome web app**. The web app opens the shared office at the same site. Supply the public Mac and Windows release URLs with `hosted/build_site.py --macos-download URL --windows-download URL`; a download becomes clickable only when its URL is configured. Publish reviewed public packages. Igor’s private presentation ZIP is a separate handoff.

On Windows x64, extract the complete ZIP and double-click **Start Office Studio.cmd** for an office saved on this computer. **Open Office Studio Online.cmd** opens the operator’s hosted site in the default browser. Configure `OFFICE_STUDIO_ONLINE_URL` to that site's exact HTTPS address. Hosted sign-in opens the shared office; existing local SQLite offices do not sync automatically.

### 1. Set up the office

![Hudson Table setup with the office name, business template and brand accent](docs/setup.png)

### 2. Step inside the Office Suite

![The same Hudson Table crew inside the 3D office, with desks, room navigation and the Head Executive](docs/office-interior.png)

**Create office** opens the built-in tower in **Overview**. Choose **Desks** to see the crew seated inside. The company name, logo, colors, and crew come from the office you just created. Hudson Table is the fictional company in this walkthrough.

Use the sun and moon switch beside **New office** to change the appearance of the Studio. Dark mode also dims the 3D interior. The Studio follows your system appearance until you choose a mode, then remembers your choice in this browser at this local address.

<details>
<summary>See the saved desks, drafts and approval inbox</summary>

![Hudson Table in Desks & drafts, with a simulated draft waiting for review](docs/boardroom.png)

</details>

The [Office Suite media kit](https://github.com/mragerlp/office-studio/tree/develop/media/instagram) includes the logo, Instagram artwork, and a short film of an office being created in the app.

## Start locally

**Using a packaged build:** Extract the complete ZIP for your operating system. Double-click **Start Office Studio.command** on an Apple Silicon Mac or **Start Office Studio.cmd** on Windows x64. The launcher starts the server and opens setup in your default browser. Keep its terminal window open while you work. The platform builds include their own runtime.

**Native Mac app development:** Open [the Xcode project](macos/OfficeStudio.xcodeproj) and follow the [Mac build guide](macos/README.md) to build a double-clickable app.

**Using source:** You need Python 3.10+ and a browser. The Python standard library serves the HTML, CSS, and JavaScript directly.

Run the command for your system from the extracted or cloned `office-studio` directory.

| Windows PowerShell   | macOS Terminal         |
| -------------------- | ---------------------- |
| `py -3 -B launch.py` | `python3 -B launch.py` |

The launcher prefers the [local address on port 8765](http://127.0.0.1:8765). It chooses a free port when needed and prints the actual address. Press **Ctrl+C** in the terminal to stop.

## Create → desk → draft → review

1. **Create an office.** Add a name, optional town/service area, accent color, and optional PNG/JPEG/WebP logo. Choose a practice template or enter your own industry, such as a restaurant.
   Select **Create office** to enter your company's 3D tower. Choose **Desks** to see the crew at their workstations.
2. **Choose a desk.** Each agent has a specialty and instructions. Every new office reserves one of its ten seats for **Legal Review**, which prepares questions and drafts for the owner or qualified counsel. Open **Desk settings** to change a display title, color, provider or model. The lead desk starts as **Head Executive** and uses your business accent and optional logo.
3. **Prepare a draft.** Write a synthetic brief. The desk uses its saved provider and model by default. Choose **Local demo · this draft only** to rehearse the workflow offline. The inbox records how each draft was generated.
4. **Review the text.** Approve or decline the draft in the inbox. The decision is saved locally. Sending a message or changing a business record remains a separate owner action.

Starter crews cover general business, real estate, law, accounting, financial advisory, medical administration, scientific research and biotechnology. You can also import an intake JSON pack. Templates supply crew, rules and approval gates. Use fictional information in sample packs.

The optional **Find town on map** link opens an OpenStreetMap search only when clicked. It does not establish an exact location or fetch a map during setup.

## Give a desk a file

For a two-minute walkthrough, create a fictional office and open **Desks & drafts**.

1. Add the [sample Friday inquiry](examples/friday-inquiry.txt) under **Working file**. It is also in the extracted ZIP's `examples` folder. The local edition accepts UTF-8 `.txt` and `.md` files up to 32 KiB each.
2. Select **Guest communications · GUEST DESK** and enter “Draft a reply asking what time works. Leave availability unconfirmed.” Choose **Local demo · this draft only**. With this sample, Guest Desk prepares an offline example reply asking for the guest’s preferred time. For a live draft, review the file, provider and model shown and confirm the transfer.
3. Prepare the draft, open it in the review inbox, and approve or decline. Approval enables a text download. The draft records its desk and the version of its source file.
4. To find it again from the room, open **GUEST DESK → Delivered → View approved drafts**. Select the saved item to read its text, source version and decision.

Removing a local original revokes future access to that file. Earlier local drafts retain their text and source label. The hosted pilot uses a different retention rule: removing the original deletes its derived runs and drafts. Already downloaded or transmitted copies remain with their recipients.

**Help** at the end of the page opens the [Beyder & Co. knowledge base](https://manual.beyderco.com/) when clicked. The [bundled app guide](help.html) is also available offline. Under **Office rules & approval gates**, save a company-specific HTTPS operating-manual link. It is available from the workspace header and from **The Field** in a compatible room. The app opens the manual on request. It does not crawl the site or give model providers its contents.

## Inside the 3D office

The source checkout and both platform packages include Igor Beyder's room and the Three.js renderer. Launch Office Studio and choose or create a workspace. The app serves the scene locally and populates it with that workspace's crew. A WebGL-capable browser is required for the 3D view.

Use **Overview** for the tower, **The Hudson** for the river, **Desks** to visit your crew, **Market Room** for the boardroom, and **Data Wall** for the displays. **The Door** takes you to the entrance. **Task board** shows the room's simulated activity. **Add agent** in the embedded room opens the saved workspace form. Use **Desks & drafts** to configure models, prepare a draft or record an owner decision.

To use another compatible room locally, place it beside the launcher as `private-room.html` or pass `--room-file`, then restart. The renderer runs on a separate loopback origin. [Three.js license](assets/three-LICENSE.txt)

## Storage and model providers

The server listens on loopback and saves offices, uploaded logos, drafts, and decisions in SQLite at `~/.office-studio/office.sqlite3` in your user home. Set `--data-dir` to choose another folder. All workspaces belong to the same local operator and depend on the host computer's access controls and disk protection.

New desks default to the offline demo. You can save a host-allowed model preference before adding an API key. If the provider is unavailable, live drafting stays disabled until it is configured or you explicitly select the demo.

The local app retains a request token for an interrupted submission, including a brief without a file. Retrying the same request can recover its saved result. An interrupted offline demo can resume; an uncertain live call stays held to avoid automatically charging twice. Incomplete provider replies are rejected instead of becoming approvable drafts. These local protections do not establish hosted recovery or live provider access.

To start a session with live providers, open **Configure Providers.command** on macOS or **Configure Providers.cmd** on Windows. Choose a provider, enter the model IDs available to your account, then enter its API key in the hidden terminal prompt. Repeat for another provider or press Enter to launch. These settings last for that server session. Alternatively, configure the following environment variables before launch.

| Provider | API key variable    | Default model            | Optional allowed models   |
| -------- | ------------------- | ------------------------ | ------------------------- |
| OpenAI   | `OPENAI_API_KEY`    | `OFFICE_OPENAI_MODEL`    | `OFFICE_OPENAI_MODELS`    |
| Claude   | `ANTHROPIC_API_KEY` | `OFFICE_ANTHROPIC_MODEL` | `OFFICE_ANTHROPIC_MODELS` |
| Gemini   | `GEMINI_API_KEY`    | `OFFICE_GEMINI_MODEL`    | `OFFICE_GEMINI_MODELS`    |
| Meta Muse | `MODEL_API_KEY` | `OFFICE_META_MODEL` | `OFFICE_META_MODELS` |

API keys stay in the server process. A live draft sends the brief, agent instructions, and workspace rules to the selected provider. A successful API response verifies access to that particular model. Consumer account sign-in and business system integrations remain future work.

Provider setup references are available from [OpenAI](https://developers.openai.com/api/docs/quickstart), [Anthropic](https://platform.claude.com/docs/en/api/overview), [Google](https://ai.google.dev/gemini-api/docs/api-key), and [Meta](https://dev.meta.ai/docs/overview).

## Supabase

**Local and hosted editions.** The packaged app stores offices in SQLite. The separate hosted file pilot uses Supabase Auth, private Postgres rows and a server-side drafting function. A signed-in owner creates an office, gives a desk a text file, reviews its draft and downloads the approved result. Igor's 3D room displays the office's desk names, colors and review status. The host supplies its own project, OAuth application configuration and HTTPS site. [Hosted setup, limits and tests](hosted/README.md)

**Developer setup.** In PowerShell or Terminal, replace `YOUR_PROJECT_REF` with the reference for your development project and keep the URL quoted. Complete the Supabase authorization in your browser. Use `codex mcp get supabase` to inspect the configured endpoint and `codex mcp list` to check the authentication method.

```sh
codex mcp add supabase --url "https://mcp.supabase.com/mcp?project_ref=YOUR_PROJECT_REF&features=docs%2Caccount%2Cdatabase%2Cdebugging%2Cdevelopment%2Cfunctions%2Cbranching%2Cfeedback"
```

The project reference scopes the connection and disables account-wide tools, even with `account` in the requested groups. For a read-only review, append `&read_only=true` inside the quotes. Each contributor authorizes their own account. Keep developer tokens and privileged keys out of the browser app, repository and ZIPs. [Supabase MCP options](https://supabase.com/docs/guides/ai-tools/mcp)

**Business account and connections.** The hosted sign-in flow supports Apple, Google (including Gmail accounts), and Microsoft (including Outlook accounts when enabled by the tenant). Continue with ChatGPT is an opt-in partner integration requiring registration and a verified staging configuration. A separate server-side API connection authorizes live drafting for each desk. Gmail and Outlook mailbox access, consumer subscription sign-in for models, and customer billing are future work. [Google sign-in](https://supabase.com/docs/guides/auth/social-sign-in/auth-google) · [Microsoft sign-in](https://supabase.com/docs/guides/auth/social-sign-in/auth-azure) · [Row-level security](https://supabase.com/docs/guides/database/postgres/row-level-security)

## Check and package

Run the server and provider checks, then build the handoff package.

```powershell
# Windows
py -3 -B -m unittest -v
py -3 -B package.py
```

On macOS, use `python3` in place of `py -3`. Tests exercise the local HTTP API, restart persistence and model selection with synthetic data and mocked provider responses.

With a disposable Studio instance running and Playwright available, run `node tests/idle-mark.cjs http://127.0.0.1:PORT` using the printed port to check the idle header in both themes. Set `PLAYWRIGHT_MODULE` and `CHROME_PATH` to use an existing browser installation.

The browser regressions start their own disposable local server. On Windows, run `node tests/frontend-reconciliation.cjs`; on macOS, run `PYTHON="$(command -v python3)" node tests/frontend-reconciliation.cjs`. They use an existing Playwright/Chrome installation and make no live provider calls. Native Mac lifecycle checks remain in `macos/tests/test_app.py` and must run on the built Mac app.

Packaging writes the source edition to `dist/office-studio.zip` from an explicit file list. It includes the 3D room, renderer, launchers, tests, walkthrough images and five packs. Use `--runner` for a platform executable. For a private handoff with a different room, use `--private-room`.

## Development

For the next product phase, see the [scaling and department-floor research](https://github.com/mragerlp/office-studio/blob/develop/docs/research/2026-11-03-scaling/README.md), checked November 3, 2026. It covers team sign-in, provider and mailbox connections, persistent work, and lower floors within the existing skyscraper, with primary sources and proposed release checks.

For your first contribution, start with the [shared agent guide](AGENTS.md). There are short entry guides for [Muse Code](MUSE.md), [Gemini CLI](GEMINI.md), [Claude Code](CLAUDE.md), and [Codex or ChatGPT](CODEX.md).

Daily work targets `develop`, the default branch. Open feature pull requests into `develop`. Promote a tested revision to `main` through a separate release pull request after owner review. The **Check Office Studio** workflow tests and builds a public platform ZIP on Windows and macOS. [View workflow runs](https://github.com/mragerlp/office-studio/actions/workflows/check.yml).

## Direction

The next spatial feature is a floor for each department. For example, an owner could enter the accounting floor, select a desk, and open its saved work. Department floors and placement at a verified geographic location are planned.

A future voice interface would let the owner brief the Head Executive. The current app accepts written briefs and saves per-desk model choices in **Desk settings**.

The ampersand artwork uses the Old Standard bold glyph from [the upstream typeface](https://github.com/google/fonts/tree/a01f27e9f42b5afad05090256d0d809928d84cae/ofl/oldstandardtt), matching the silhouette used for the room sculpture. The [font license](assets/OFL-Old-Standard.txt) accompanies the artwork.
