# Hosted Office Studio pilot

This is the web edition of **choose a text file → assign a desk → review its draft**. It uses Supabase Auth, private rows in Postgres and an Edge Function for provider connections. The desktop launchers use their own local SQLite data. A hosted sign-in opens that user's hosted offices.

## A first walkthrough

Sign in with a Google, Microsoft or Apple account enabled by the host. Create an office with a name and color. The room opens with Head Executive, Intake and Legal Review. Select **Add a desk** to name a new desk and give it a specialty. The office holds up to ten desks including Legal Review. New desks start on the sample route.

Upload a fictional UTF-8 text file, select it and a desk, enter a brief, then select **Prepare draft**. The default route creates a sample inside the hosted service. Review the output, record a decision, and download the approved text. **Download original** returns the selected source file separately.

Under **Connections & desk settings**, an owner can connect OpenAI, Claude, Gemini or Meta Muse using the business's API key. Saving a key configures a route. A successful generation demonstrates that the credential can use the selected model. Choose an allowed model for a desk and save it. During drafting, the owner sees the file name, provider and model and explicitly permits the transfer. Office sign-in grants identity access. Mailbox connections and model billing are separate.

## Set up a private staging deployment

Use a dedicated Supabase project with the Data API enabled and the `public` schema exposed. Limit the initial pilot to test users allowed by your identity provider. Each signed-in owner can create up to twelve offices. Under **Authentication → Providers**, configure the Google, Azure (Microsoft) or Apple providers you offer. Register the Supabase callback URL shown there with each provider. In Supabase's redirect allowlist, enter the exact HTTPS page where Studio is served, including its path and trailing slash. Supabase redirects back to Studio with a single-use code. Studio exchanges it using PKCE and keeps the session in the browser tab. [Google](https://supabase.com/docs/guides/auth/social-sign-in/auth-google) · [Microsoft](https://supabase.com/docs/guides/auth/social-sign-in/auth-azure) · [PKCE](https://supabase.com/docs/guides/auth/sessions/pkce-flow)

**Apple.** In Apple Developer, enable Sign in with Apple on the primary App ID and associate a web Services ID. Register your Supabase project's domain and its HTTPS `/auth/v1/callback` as the return URL. Apple posts the authorization result to that endpoint. In Supabase, put the Services ID first in the Apple client IDs and supply its signed client secret. Keep the signing key private and renew the secret before it expires (at most six months). [Supabase Apple setup](https://supabase.com/docs/guides/auth/social-sign-in/auth-apple) · [Apple web authorization](https://developer.apple.com/documentation/signinwithapple/incorporating-sign-in-with-apple-into-other-platforms)

**Optional ChatGPT sign-in.** The button is disabled by default. OpenAI offers hosted website sign-in through a selected-partner trial. Start with an approved client, its registered token authentication method and the exact Supabase callback for staging. Configure a Supabase **OIDC** provider named `custom:chatgpt` with the assigned issuer, discovery URL and `openid profile email` identity scopes. Keep any client secret on the server. Enable upstream PKCE and nonce validation. [OpenAI website guide](https://developers.openai.com/siwc/website) · [Supabase custom providers](https://supabase.com/docs/guides/auth/custom-oauth-providers)

Verify compatibility in private staging before adding `--enable-chatgpt-sign-in` to the public site build. OpenAI can return only an ID token. The current Supabase custom provider uses an OAuth exchange that requires an access token, so an ID-token-only response fails. Verify that the broker validates the ID token signature, issuer, audience, expiry and nonce for the approved client. Check that returning users are identified by their subject, and test missing or unverified email and collisions with existing accounts. OpenAI requires confirmation for account linking on an email match, while Supabase documents automatic same-email linking. Keep the option off unless the staging provider satisfies both contracts. [OpenAI identity and linking requirements](https://developers.openai.com/siwc/website) · [Supabase exchange](https://github.com/supabase/auth/blob/master/internal/api/provider/custom_oauth.go) · [OAuth token parser](https://github.com/golang/oauth2/blob/v0.36.0/internal/token.go) · [Supabase identity linking](https://supabase.com/docs/guides/auth/auth-identity-linking)

Review the [migration](../supabase/migrations/20261103000100_office_studio_pilot.sql) before provisioning. From the repository root, link the Supabase CLI to the staging project, check the migration list and dry run, then apply the migration and deploy the single function. The function validates user tokens against the project's Auth service before its privileged database calls.

```sh
supabase link --project-ref YOUR_STAGING_PROJECT_REF
supabase migration list
supabase db push --dry-run
supabase db push
supabase functions deploy office-drafts
```

Set the following Edge Function secrets through the Supabase dashboard or a private, untracked environment file. Use the deployed site's exact origin (scheme and host, no path) for `STUDIO_WEB_ORIGIN`. Supabase supplies the project URL and server API keys to the function. Its public and secret API key dictionaries are supported through their `default` entry, with legacy anon/service-role keys as a fallback. [Function secrets](https://supabase.com/docs/guides/functions/secrets)

| Setting | Purpose |
| --- | --- |
| `STUDIO_WEB_ORIGIN` | Allowed web origin for the draft broker, such as `https://office.example.com`. |
| `STUDIO_KEY_ENCRYPTION` | Base64 encoding of 32 cryptographically random bytes. Required for saving or using live keys. Keep in a secrets manager, with a recovery copy. |
| `STUDIO_OPENAI_MODELS`, `STUDIO_ANTHROPIC_MODELS`, `STUDIO_GEMINI_MODELS`, `STUDIO_META_MODELS` | Comma-separated model IDs for that provider. Use IDs enabled on the pilot accounts. An empty setting disables live setup for that provider. |

Set **only** `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in the static site's build environment. Run the following from the repository root and serve `dist/hosted` over HTTPS. A static host such as Vercel can use this build command and output directory. The Python build bundles Igor's room and local Three.js. A local preview can use a loopback HTTP server and a separately configured loopback redirect. The project reference and publishable key are public client configuration.

```sh
python -B hosted/build_site.py
```

## Data, permissions and deletion

| Record | Who can access it | Lifecycle |
| --- | --- | --- |
| Office, membership and desks | Signed-in members can read their own office. The creator is its owner and only initial member. Owner actions are checked at the database or broker boundary. | The starter desks, selected model and office accent persist. Team invites and member administration are future work. |
| Source file | Members of its office can read it. Only an owner can upload or remove it. The UI accepts plain `.txt` up to 64 KiB, with a separate immutable ID for each upload. | An office holds up to 64 source files. **Delete selected file** removes the source and its derived drafts from active Postgres rows. |
| Draft and decision | An authorized owner chooses a single file, brief, desk and destination. The broker sends only the selected file name/text, brief and desk instructions to the chosen fixed provider. The 3D frame receives desk names and review indicators. | Up to 256 current drafts per office. The owner approves or declines a completed draft once. Copies already downloaded or passed to a provider follow their separate retention policies. |
| Provider key | Submitted over HTTPS directly to the broker. Each office/provider pair is encrypted with AES-GCM and a fresh nonce. The browser receives connection status. The service-role credential and encryption secret stay server-side. | Reconnecting replaces the ciphertext. **Disconnect** removes the live connection. A previously claimed in-flight request may finish. After master-key rotation, reconnect affected providers or perform an independently reviewed re-encryption procedure. |
| Used request IDs | The database retains IDs with their kind and office, without file content or briefs. | IDs remain spent after deleting a source. An old retry or provider response cannot attach to a later assignment. Receipts and all office records cascade on office deletion. Backups follow the host's retention policy. |

Retries with the same request ID reuse its original draft. An interrupted live call can leave a preparing run; retrying that request after three minutes marks it failed without making a second provider call. Starting another attempt after a confirmed failure can incur a new provider charge. Review the provider account if delivery was ambiguous. The hosted pilot performs text drafting. Approving a result records a decision in the office.

## Check the pilot

From the repository root:

```sh
node --test hosted/tests/auth.test.cjs
deno test supabase/functions/office-drafts/handler_test.js
deno check supabase/functions/office-drafts/index.ts
```

The following sequence exercises tenant isolation, retry receipts, file and draft deletion, stale credential revisions and review finality in a **fresh, disposable vanilla PostgreSQL database**. The fixture only simulates the Supabase roles and authenticated identity. Never run it in a linked project.

```sh
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f hosted/tests/postgres-fixture.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20261103000100_office_studio_pilot.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/office_pilot.sql
```

Before inviting pilot users, test the actual OAuth redirect from two dedicated test accounts on the deployed origin. Verify that each office sees only its own identically named synthetic file and cannot act on the other office's IDs. Review a sample draft, delete its file, disconnect the provider and sign out. Live provider billing and provider-side retention depend on each business's account. [OpenAI](https://platform.openai.com/docs/api-reference/responses/create) · [Claude](https://platform.claude.com/docs/en/api/messages/create) · [Gemini](https://ai.google.dev/api/generate-content) · [Meta Muse](https://dev.meta.ai/docs/overview)
