# Office Studio

Office Studio is a local web app for your business's crew. Give the Head Executive a brief for the morning meeting, or ask a specialist to draft a client update. Each desk can use a different model. The owner reviews the draft and records a decision in the boardroom.

![Office Studio's desk floor and approval inbox, using a fictional restaurant and simulated draft](docs/boardroom.png)

_The Desks & drafts view, shown with a fictional restaurant and simulated output._

## Start locally

**Using a packaged build:** Extract the complete ZIP for your operating system. Double-click **Start Office Studio.command** on an Apple Silicon Mac or **Start Office Studio.cmd** on Windows x64. The launcher starts the server and opens setup in your default browser. Keep its terminal window open while you work. The platform builds include their own runtime.

**Using source:** You need Python 3.10+ and a browser. The Python standard library serves the HTML, CSS, and JavaScript directly.

Run the command for your system from the extracted or cloned `office-studio` directory.

| Windows PowerShell   | macOS Terminal         |
| -------------------- | ---------------------- |
| `py -3 -B launch.py` | `python3 -B launch.py` |

The launcher prefers the [local address on port 8765](http://127.0.0.1:8765). It chooses a free port when needed and prints the actual address. Press **Ctrl+C** in the terminal to stop.

## Create → desk → draft → review

1. **Create an office.** Add a name, optional town/service area, accent color, and optional PNG/JPEG/WebP logo. Choose a practice template or enter your own industry, such as a restaurant.
   If the owner has supplied a compatible room file, the new office opens in the 3D tower's **Overview** with its selected crew. Otherwise it opens directly to **Desks & drafts**.
2. **Choose a desk.** Each agent has a specialty and instructions. Open **Desk settings** to change its display title and color or select its provider and model. The lead desk starts as **Head Executive** and uses your business accent and optional logo. Add agents as needed, up to ten desks per office.
3. **Prepare a draft.** Write a synthetic brief. The desk uses its saved provider and model by default. Choose **Local demo · this draft only** to rehearse the workflow offline. The inbox records how each draft was generated.
4. **Review the text.** Approve or decline the draft in the inbox. The decision is saved locally. Sending a message or changing a business record remains a separate owner action.

Starter crews cover general business, real estate, law, accounting, financial advisory, medical administration, scientific research and biotechnology. You can also import an intake JSON pack. Templates supply crew, rules and approval gates. Use fictional information in sample packs.

The optional **Find town on map** link opens an OpenStreetMap search only when clicked. It does not establish an exact location or fetch a map during setup.

**Help** opens the bundled product guide, even offline. Under **Office rules & approval gates**, save a company-specific HTTPS operating-manual link. It is available from the workspace header and from **The Field** in a compatible room. The app opens the manual on request. It does not crawl the site or give model providers its contents.

## Optional private 3D room

Place an owner-supplied, pack-compatible HTML room beside the launcher as `private-room.html`, or pass its path with `--room-file`. Restart the app. A separate loopback port serves the room with a presentation adapter. It applies the office name, logo, colors and desk titles at runtime while preserving the original file on disk. Its pack contains the office title, crew, rules and gates. The public build includes the adapter and synthetic fixtures. The room artwork is supplied separately by its owner.

Use **Overview** for the building, **Desks** to move inside and **Market Room** for the boardroom. Room activity is simulated. Switch to **Desks & drafts** in Office Studio to configure a model, generate a draft or record a saved decision. The compatible room uses Three.js r128 from cdnjs and requires WebGL. Your saved workspace remains accessible in the desk view.

## Storage and model providers

The server listens on loopback and saves offices, uploaded logos, drafts, and decisions in SQLite at `~/.office-studio/office.sqlite3` in your user home. Set `--data-dir` to choose another folder. All workspaces belong to the same local operator and depend on the host computer's access controls and disk protection.

New desks default to the offline demo. You can save a host-allowed model preference before adding an API key. If the provider is unavailable, live drafting stays disabled until it is configured or you explicitly select the demo.

To start a session with live providers, open **Configure Providers.command** on macOS or **Configure Providers.cmd** on Windows. Choose a provider, enter the model IDs available to your account, then enter its API key in the hidden terminal prompt. Repeat for another provider or press Enter to launch. These settings last for that server session. Alternatively, configure the following environment variables before launch.

| Provider | API key variable    | Default model            | Optional allowed models   |
| -------- | ------------------- | ------------------------ | ------------------------- |
| OpenAI   | `OPENAI_API_KEY`    | `OFFICE_OPENAI_MODEL`    | `OFFICE_OPENAI_MODELS`    |
| Claude   | `ANTHROPIC_API_KEY` | `OFFICE_ANTHROPIC_MODEL` | `OFFICE_ANTHROPIC_MODELS` |
| Gemini   | `GEMINI_API_KEY`    | `OFFICE_GEMINI_MODEL`    | `OFFICE_GEMINI_MODELS`    |
| Meta Muse | `MODEL_API_KEY` | `OFFICE_META_MODEL` | `OFFICE_META_MODELS` |

API keys stay in the server process. A live draft sends the brief, agent instructions, and workspace rules to the selected provider. A successful API response verifies access to that particular model. Consumer account sign-in and business system integrations remain future work.

Provider setup references are available from [OpenAI](https://developers.openai.com/api/docs/quickstart), [Anthropic](https://platform.claude.com/docs/en/api/overview), [Google](https://ai.google.dev/gemini-api/docs/api-key), and [Meta](https://dev.meta.ai/docs/overview).

## Check and package

Run the server and provider checks, then build the handoff package.

```powershell
# Windows
py -3 -B -m unittest -v
py -3 -B package.py
```

On macOS, use `python3` in place of `py -3`. Tests exercise the local HTTP API, restart persistence and model selection with synthetic data and mocked provider responses.

Packaging writes the source edition to `dist/office-studio.zip` from an explicit file list. It includes the launchers, tests, screenshot, and five packs. For a private owner handoff, the packager accepts `--runner` for a platform executable and `--private-room` for the owner's HTML. Keep private handoff ZIPs out of version control and public workflow artifacts.

## Development

Daily work targets `develop`, the default branch. Open feature pull requests into `develop`. Promote a tested revision to `main` through a separate release pull request after owner review. The **Check Office Studio** workflow tests and builds a public platform ZIP on Windows and macOS. [View workflow runs](https://github.com/mragerlp/office-studio/actions/workflows/check.yml).

## Direction

The next spatial feature is a floor for each department. For example, an owner could enter the accounting floor, select a desk, and open its saved work. Department floors and placement at a verified geographic location are planned.

A future voice interface would let the owner brief Crimson, review a proposed change to the office, and approve it. The current app accepts written briefs and saves per-desk model choices in **Desk settings**.
