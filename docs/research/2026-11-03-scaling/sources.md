# Research sources and evidence boundary

Checked November 3, 2026, using primary documentation, GitHub API and selected pinned source reads. Unversioned documentation is a dated snapshot. Recheck it when implementing. No pricing quote, production capacity, provider approval, integration deployment or competitor runtime test is established here.

## StarNet

GitHub API identified the repository's default branch as `feat/harness-backend` and its checked HEAD as `74fcd5040ba0eb93c8f9fa07b2d0a9fcfddd1475`, committed October 29, 2026. Source links below fix that revision.

- [Provider factory](https://github.com/androoAGI/starnet/blob/74fcd5040ba0eb93c8f9fa07b2d0a9fcfddd1475/sidecar/providers/factory.js) selects an adapter behind a common route.
- [Provider interface](https://github.com/androoAGI/starnet/blob/74fcd5040ba0eb93c8f9fa07b2d0a9fcfddd1475/sidecar/providers/provider.js) describes normalized events and provider-specific replay requirements.
- [Account storage](https://github.com/androoAGI/starnet/blob/74fcd5040ba0eb93c8f9fa07b2d0a9fcfddd1475/sidecar/provider-accounts.js) separates account metadata and credential locations. Its multiple-account behavior is an observation, not an Office Studio recommendation.
- [Budget caps](https://github.com/androoAGI/starnet/blob/74fcd5040ba0eb93c8f9fa07b2d0a9fcfddd1475/sidecar/budgetcaps.js) resolves and validates budget settings.
- [Workspace safety](https://github.com/androoAGI/starnet/blob/74fcd5040ba0eb93c8f9fa07b2d0a9fcfddd1475/sidecar/workspace-safety.js) identifies user-data roots protected from development operations.
- [Claude CLI adapter documentation](https://github.com/androoAGI/starnet/blob/74fcd5040ba0eb93c8f9fa07b2d0a9fcfddd1475/docs/CLAUDE_CLI_PROVIDER.md) describes driving the user's own CLI and leaving its credentials with the CLI. This is distinct from offering Claude.ai OAuth within a third-party web app.

Inspection was bounded to those source files and metadata. It does not establish StarNet's hosted tenant isolation, security, throughput or integration permission. No source was copied into Office Studio.

## Comparable applications and execution patterns

- [LibreChat agents](https://www.librechat.ai/docs/features/agents), [file search](https://www.librechat.ai/docs/features/rag_api), [access controls](https://www.librechat.ai/docs/features/access_control).
- [Dify Human Input](https://docs.dify.ai/en/cloud/use-dify/nodes/human-input), [model providers](https://docs.dify.ai/en/cloud/use-dify/workspace/model-providers). The provider page was reached through the official documentation navigation after an outdated path failed.
- [n8n queue mode](https://docs.n8n.io/hosting/scaling/queue-mode/). Documented Redis/database/worker architecture is a pattern comparison, not a dependency selection.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence).
- [LiteLLM virtual keys](https://docs.litellm.ai/docs/proxy/virtual_keys). Feature availability and hosting requirements need a version-specific evaluation before adoption.

## Identity, model connections and mail

- [Supabase social sign-in](https://supabase.com/docs/guides/auth/social-sign-in) explains separate provider tokens and application-managed provider-token refresh.
- [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security) and [Storage access](https://supabase.com/docs/guides/storage/security/access-control) describe access policies and privileged-key bypass. Context7 resolved `/supabase/supabase` and returned primary source excerpts for those boundaries. Tenant membership enforcement is our proposed application design.
- [OpenAI sign-in quickstart](https://developers.openai.com/siwc/quickstart), [open-source/local plan usage](https://developers.openai.com/siwc/token-sharing-open-source), [Codex app-server route](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server). Local/open-source plan usage and paid/remote eligibility have different registration requirements. A returned model catalog is not an entitlement check.
- [Anthropic authentication and credential rules](https://code.claude.com/docs/en/legal-and-compliance). API-based third-party drafting and an unmodified Claude Code instance are distinct paths.
- [Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key), [Gemini OAuth](https://ai.google.dev/gemini-api/docs/oauth). The OAuth quickstart includes testing-oriented examples that need production review.
- [Meta Model API overview](https://dev.meta.ai/docs/overview). Documents the API bearer credential and Muse Code's own sign-in. It does not establish an approved Office Studio web subscription-login flow.
- [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes), [restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification). Requirements depend on scopes, data handling and applicable exceptions.
- [Microsoft delegated access](https://learn.microsoft.com/en-us/graph/auth-v2-user), [permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference), [subscription lifecycle](https://learn.microsoft.com/en-us/graph/api/resources/subscription?view=graph-rest-1.0). Confirm the current narrow scopes and organizational consent requirements during implementation.

## Hosting and business operations

- [Supabase Queues](https://supabase.com/docs/guides/queues) documents visibility-window delivery. This does not make external sends or billing exactly once.
- [Vercel Workflows](https://vercel.com/docs/workflows) documents durable resumable execution. Function duration and plan limits change, so this research makes no fixed duration or cost commitment.
- [Stripe subscription webhooks](https://docs.stripe.com/billing/subscriptions/webhooks), [webhook event handling](https://docs.stripe.com/webhooks). Handle duplicate and out-of-order events.
- [Supabase backups](https://supabase.com/docs/guides/platform/backups). Database backups exclude uploaded Storage object contents.

## Baseline and open checks

Office Studio's README, AGENTS, hosted README, migration, room renderer and room adapter were read at release `9020047246ac1251e23faeb6a962593fcdf63a81`. The migration has office-membership authorization and initial owner membership. Invitations and administration need additional paths. The room adapter preserves a separate minimal display boundary.

The original Mac test gate remains in force. Muse cleared the exact private presentation ZIP for beginning that rehearsal on the basis of its public-build check plus VENGEANCE's file comparison. Physical Finder launch, Gatekeeper behavior and GPU rendering remain pending. Research publishing does not change the reviewed application baseline or sealed handoff ZIP.
