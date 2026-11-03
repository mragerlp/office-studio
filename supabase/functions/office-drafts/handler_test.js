import { handler } from "./handler.js";

const A = "00000000-0000-4000-8000-000000000001", B = "00000000-0000-4000-8000-000000000002";
const OFFICE = "00000000-0000-4000-8000-000000000010", DESK = "00000000-0000-4000-8000-000000000011";
const FILE = "00000000-0000-4000-8000-000000000012", RUN = "00000000-0000-4000-8000-000000000013";
const ORIGIN = "https://office.example.test", SBASE = "https://db.example.test";
const USER_TOKEN = "synthetic-user-access-token",
  SERVICE = "fixture-service",
  KEY = "example-key-value-for-testing";
const expect = (value, message = "assertion failed") => {
  if (!value) throw new Error(message);
};
const json = (value, status = 200) => new Response(JSON.stringify(value), { status });
function fixture() {
  const config = {
    SUPABASE_URL: SBASE,
    SUPABASE_ANON_KEY: "public",
    SUPABASE_SERVICE_ROLE_KEY: SERVICE,
    STUDIO_WEB_ORIGIN: ORIGIN,
    STUDIO_KEY_ENCRYPTION: btoa("a".repeat(32)),
    STUDIO_OPENAI_MODELS: "model-1",
    STUDIO_ANTHROPIC_MODELS: "model-1",
    STUDIO_GEMINI_MODELS: "model-1",
    STUDIO_META_MODELS: "model-1",
  };
  const state = {
    user: A,
    desk: { name: "Intake", provider: "demo", model: "" },
    connections: {},
    runs: {},
    sent: [],
    db: [],
    failProvider: false,
  };
  async function send(raw, opts) {
    const u = new URL(raw), h = new Headers(opts.headers), data = opts.body && JSON.parse(opts.body);
    if (u.origin === SBASE && u.pathname === "/auth/v1/user") {
      expect(h.get("authorization") === "Bearer " + USER_TOKEN);
      expect(h.get("apikey") === "public");
      return json({ id: state.user });
    }
    if (u.origin !== SBASE) {
      state.sent.push({ url: u.href, h, data });
      expect(opts.redirect === "error");
      expect(!JSON.stringify(opts.headers).includes(SERVICE));
      if (state.failProvider) return json({ error: "do not expose provider details" }, 403);
      if (u.hostname === "api.openai.com") {
        return json({
          output: [{ type: "message", content: [{ type: "output_text", text: "OpenAI result" }] }],
        });
      }
      if (u.hostname === "api.anthropic.com") {
        return json({ content: [{ type: "text", text: "Claude result" }] });
      }
      if (u.hostname === "generativelanguage.googleapis.com") {
        return json({
          candidates: [{
            content: { parts: [{ thought: true, text: "internal" }, { text: "Gemini result" }] },
          }],
        });
      }
      if (u.hostname === "api.meta.ai") return json({ choices: [{ message: { content: "Muse result" } }] });
      throw Error("Unexpected host");
    }
    expect(h.get("authorization") === "Bearer " + SERVICE);
    state.db.push(u.pathname);
    const q = u.searchParams, table = u.pathname.split("/").pop(), p = q.get("provider")?.slice(3);
    if (table === "office_studio_offices") {
      return json(q.get("id") === "eq." + OFFICE && q.get("owner_id") === "eq." + A ? [{ id: OFFICE }] : []);
    }
    if (table === "office_studio_desks") {
      if (q.get("id") !== "eq." + DESK || q.get("office_id") !== "eq." + OFFICE) return json([]);
      if (opts.method === "PATCH") Object.assign(state.desk, data);
      return json([state.desk]);
    }
    if (table === "office_studio_connections") {
      if (opts.method === "DELETE") {
        delete state.connections[p];
        return json([]);
      }
      if (opts.method === "POST") {
        state.connections[data.provider] = data;
        return json([]);
      }
      return json(
        p
          ? (state.connections[p] ? [state.connections[p]] : [])
          : Object.values(state.connections).map((r) => ({ provider: r.provider })),
      );
    }
    if (table === "office_studio_files") {
      return json(
        q.get("id") === "eq." + FILE && q.get("office_id") === "eq." + OFFICE
          ? [{ name: "inquiry.txt", content: "A test inquiry" }]
          : [],
      );
    }
    if (table === "office_studio_reserve") {
      if (state.runs[data.p_id]) return json({ fresh: false, status: state.runs[data.p_id].status });
      state.runs[data.p_id] = { id: data.p_id, status: "preparing" };
      return json({ fresh: true, status: "preparing" });
    }
    if (table === "office_studio_runs") {
      const r = state.runs[q.get("id").slice(3)];
      Object.assign(r, data);
      return json([r]);
    }
    throw Error("Unexpected database route");
  }
  const serve = handler(config, send);
  const invoke = (action, props = {}, opts = {}) =>
    serve(
      new Request("https://edge.example.test/office-drafts", {
        method: "POST",
        headers: {
          Origin: ORIGIN,
          Authorization: "Bearer " + USER_TOKEN,
          "content-type": "application/json",
          ...opts,
        },
        body: JSON.stringify({ action, office: OFFICE, ...props }),
      }),
    );
  const assignment = (provider = "demo") => ({
    desk: DESK,
    file: FILE,
    run: RUN,
    brief: "Draft a reply",
    provider,
    model: provider === "demo" ? "" : "model-1",
  });
  return { invoke, assignment, state };
}

Deno.test("only the authenticated office owner can access the broker", async () => {
  const { invoke, state } = fixture();
  expect((await invoke("status", {}, { Origin: "https://intruder.example.test" })).status === 403);
  expect(state.db.length === 0);
  expect((await invoke("status", {}, { Authorization: "" })).status === 401);
  expect(state.db.length === 0);
  state.user = B;
  expect((await invoke("connect", { provider: "openai", key: KEY })).status === 403);
  expect(!state.db.includes("/rest/v1/office_studio_connections"));
  expect(state.sent.length === 0);
});
Deno.test("sample uses saved source and retry never sends a request to a provider", async () => {
  const f = fixture();
  let result = await f.invoke("draft", f.assignment());
  expect(result.ok);
  expect(f.state.runs[RUN].body.includes("A test inquiry"));
  result = await f.invoke("draft", f.assignment());
  expect(result.ok);
  expect(f.state.sent.length === 0);
  expect((await f.invoke("draft", { ...f.assignment(), file: B })).status === 404);
});
for (
  const [provider, domain, body] of [
    ["openai", "api.openai.com", "OpenAI result"],
    ["anthropic", "api.anthropic.com", "Claude result"],
    ["gemini", "generativelanguage.googleapis.com", "Gemini result"],
    ["meta", "api.meta.ai", "Muse result"],
  ]
) {
  Deno.test(
    provider + " uses the selected file, fixed host, office-bound key and explicit consent",
    async () => {
      const f = fixture(), selected = { provider, model: "model-1", desk: DESK };
      expect((await f.invoke("connect", { provider, key: KEY })).ok);
      const sealed = f.state.connections[provider].sealed_key;
      expect(sealed && !sealed.includes(KEY));
      const status = await (await f.invoke("status")).text();
      expect(!status.includes(KEY) && !status.includes(sealed));
      expect((await f.invoke("route", { ...selected, model: "forbidden" })).status === 400);
      expect((await f.invoke("route", selected)).ok);
      expect((await f.invoke("draft", f.assignment(provider))).status === 400);
      expect(
        (await f.invoke("draft", { ...f.assignment(provider), consent: true, model: "stale" })).status ===
          409,
      );
      expect(f.state.sent.length === 0);
      expect((await f.invoke("draft", { ...f.assignment(provider), consent: true })).ok);
      expect(f.state.sent.length === 1 && new URL(f.state.sent[0].url).hostname === domain);
      expect(f.state.runs[RUN].body === body);
      const payload = JSON.stringify(f.state.sent[0].data);
      expect(
        payload.includes("A test inquiry") && payload.includes("Draft a reply") && !payload.includes(KEY),
      );
      expect((await f.invoke("draft", { ...f.assignment(provider), consent: true })).ok);
      expect(f.state.sent.length === 1, "duplicate external call");
      expect((await f.invoke("disconnect", { provider })).ok);
      expect((await f.invoke("draft", { ...f.assignment(provider), consent: true, run: B })).status === 409);
      expect(f.state.sent.length === 1);
    },
  );
}
Deno.test("provider substitution fails decryption and provider errors leave a failed run", async () => {
  const f = fixture();
  await f.invoke("connect", { provider: "openai", key: KEY });
  f.state.connections.anthropic = { ...f.state.connections.openai, provider: "anthropic" };
  await f.invoke("route", { desk: DESK, provider: "anthropic", model: "model-1" });
  let response = await f.invoke("draft", { ...f.assignment("anthropic"), consent: true });
  expect(response.status === 502 && f.state.sent.length === 0);
  await f.invoke("route", { desk: DESK, provider: "openai", model: "model-1" });
  f.state.failProvider = true;
  response = await f.invoke("draft", { ...f.assignment("openai"), consent: true });
  expect(response.status === 502 && f.state.runs[RUN].status === "failed" && !f.state.runs[RUN].body);
  expect(!(await response.text()).includes("do not expose"));
});
