# Office Studio

Office Studio is a local web app for running a business's agent desks. Give Crimson, the chief of staff, a brief for the morning meeting, or ask a specialist to draft a client update. Each desk can use a different model. The owner reviews the draft and records a decision in the boardroom.

![Office Studio's desk floor and approval inbox, using a fictional restaurant and simulated draft](docs/boardroom.png)

_The current 2D app, shown with synthetic information and simulated output._

## Start locally

You need Python 3.10+ and a browser. The Python standard library serves the HTML, CSS, and JavaScript directly.

Run the command for your system from the extracted or cloned `office-studio` directory.

| Windows PowerShell   | macOS Terminal         |
| -------------------- | ---------------------- |
| `py -3 -B server.py` | `python3 -B server.py` |

Open [Office Studio on this computer](http://127.0.0.1:8765). Keep the terminal running. Press **Ctrl+C** to stop. Use `--port 8766` if the default port is occupied.

## Create → desk → draft → review

1. **Create an office.** Add a name, optional town/service area, accent color, and optional PNG/JPEG/WebP logo. Choose a practice template or enter your own industry, such as a restaurant.
2. **Choose a desk.** Each agent has a specialty and instructions. Open **Desk settings** to save its preferred provider and host-allowed model, including for the chief of staff. Add agents as needed, up to ten desks per office.
3. **Prepare a draft.** Write a synthetic brief. The desk uses its saved provider and model by default. Choose **Local demo · this draft only** to rehearse the workflow offline. The inbox records how each draft was generated.
4. **Review the text.** Approve or decline the draft in the inbox. The decision is saved locally. Sending a message or changing a business record remains a separate owner action.

The five synthetic practice packs cover real estate, law, accounting, financial advisory, and medical administration. You can also import an intake JSON pack. Templates supply crew, rules, and approval gates. Use fictional information in sample packs.

The optional **Find town on map** link opens an OpenStreetMap search only when clicked. It does not establish an exact location or fetch a map during setup.

## Storage and model providers

The server listens on loopback and saves offices, uploaded logos, drafts, and decisions in SQLite at `~/.office-studio/office.sqlite3` in your user home. Set `--data-dir` to choose another folder. All workspaces belong to the same local operator and depend on the host computer's access controls and disk protection.

New desks default to the offline demo. You can save a host-allowed model preference before adding an API key. If the provider is unavailable, live drafting stays disabled until it is configured or you explicitly select the demo.

To enable a provider, set its key and default model in the shell that launches the server, then restart it. Optionally set a comma-separated model allowlist for the desk-settings dropdown. Use model identifiers available to your provider account.

| Provider | API key variable    | Default model            | Optional allowed models   |
| -------- | ------------------- | ------------------------ | ------------------------- |
| OpenAI   | `OPENAI_API_KEY`    | `OFFICE_OPENAI_MODEL`    | `OFFICE_OPENAI_MODELS`    |
| Claude   | `ANTHROPIC_API_KEY` | `OFFICE_ANTHROPIC_MODEL` | `OFFICE_ANTHROPIC_MODELS` |
| Gemini   | `GEMINI_API_KEY`    | `OFFICE_GEMINI_MODEL`    | `OFFICE_GEMINI_MODELS`    |

API keys stay in the server process. A live draft sends the brief, agent instructions, and workspace rules to the selected provider. A successful API response verifies access to that particular model. Consumer account sign-in and business system integrations remain future work.

## Check and package

Run the server and provider checks, then build the handoff package.

```powershell
# Windows
py -3 -B -m unittest -v test_office.py test_providers.py
py -3 -B package.py
```

On macOS, use `python3` in place of `py -3`. Tests exercise the local HTTP API, restart persistence and model selection with synthetic data and mocked provider responses.

Packaging writes `dist/office-studio.zip` from an explicit file list, including this screenshot and the five packs. Local databases, credentials, and working folders are excluded. Extract the ZIP and use the same startup command inside its `office-studio` folder.

## Development

Daily work targets `develop`, the default branch. Open feature pull requests into `develop`. Promote a tested revision to `main` through a separate release pull request after owner review. The **Check Office Studio** workflow runs the tests and builds the ZIP on Windows and macOS. Its Windows job attaches the portable ZIP to the workflow run.

## Direction

The planned **3D office tower** gives each department a floor in one building. For example, the owner could enter the accounting floor, select its desk, and review its work. The screenshot above shows the current 2D office. The tower and placement at a verified location are planned.

A future voice interface would let the owner brief Crimson, review a proposed change to the office, and approve it. The current app accepts written briefs and saves per-desk model choices in **Desk settings**.
