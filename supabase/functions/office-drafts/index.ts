import { handler } from "./handler.js";

const config = Object.fromEntries([
  "SUPABASE_URL",
  "SUPABASE_ANON_KEY",
  "SUPABASE_SERVICE_ROLE_KEY",
  "STUDIO_WEB_ORIGIN",
  "STUDIO_KEY_ENCRYPTION",
  "STUDIO_OPENAI_MODELS",
  "STUDIO_ANTHROPIC_MODELS",
  "STUDIO_GEMINI_MODELS",
  "STUDIO_META_MODELS",
].map((name) => [name, Deno.env.get(name)]));
// New projects may disable legacy JWT API keys. Supabase supplies the current
// project keys as named JSON dictionaries. Never forward the secret to a model.
function defaultKey(name: string) {
  const keys = JSON.parse(Deno.env.get(name) || "{}");
  return typeof keys.default === "string" ? keys.default : undefined;
}
config.SUPABASE_ANON_KEY = defaultKey("SUPABASE_PUBLISHABLE_KEYS") || config.SUPABASE_ANON_KEY;
config.SUPABASE_SERVICE_ROLE_KEY = defaultKey("SUPABASE_SECRET_KEYS") || config.SUPABASE_SERVICE_ROLE_KEY;
Deno.serve(handler(config));
