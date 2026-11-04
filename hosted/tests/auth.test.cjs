const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const { webcrypto, createHash } = require("node:crypto");
const code = fs.readFileSync(path.join(__dirname, "../auth.js"), "utf8");
function setup(config = {}) {
  const map = new Map(), calls = [], responses = [];
  const location = {
    origin: "https://office.example.test",
    pathname: "/pilot/",
    hash: "",
    href: "https://office.example.test/pilot/",
    assign: (v) => {
      location.next = v;
    },
  };
  const sandbox = {
    window: { OFFICE_STUDIO_CONFIG: { url: "https://project.example.test", publishableKey: "public", ...config } },
    location,
    history: { replaceState: (_, __, u) => location.href = u },
    crypto: webcrypto,
    URL,
    URLSearchParams,
    TextEncoder,
    btoa,
    sessionStorage: {
      getItem: (k) => map.get(k) || null,
      setItem: (k, v) => map.set(k, v),
      removeItem: (k) => map.delete(k),
    },
    fetch: async (u, options) => {
      calls.push({ u, options });
      assert.ok(responses.length, "unexpected request");
      const x = responses.shift();
      return new Response(JSON.stringify(x[1]), { status: x[0] });
    },
  };
  vm.runInNewContext(code, sandbox);
  return { auth: sandbox.window.HostedAuth, location, map, calls, responses };
}
test("OAuth uses a random S256 verifier, fixed return page, and exchanges Supabase's code once", async () => {
  const f = setup();
  assert.equal(await f.auth.init(), false);
  await f.auth.login("azure");
  const authUrl = new URL(f.location.next);
  assert.equal(authUrl.host, "project.example.test");
  assert.equal(authUrl.searchParams.get("redirect_to"), "https://office.example.test/pilot/");
  assert.equal(authUrl.searchParams.get("scopes"), "email");
  const entry = JSON.parse([...f.map.values()][0]);
  assert.equal(
    createHash("sha256").update(entry.verifier).digest("base64url"),
    authUrl.searchParams.get("code_challenge"),
  );
  assert.ok(!f.location.next.includes(entry.verifier));
  f.location.href += "?code=fake-code";
  f.responses.push([200, {
    access_token: "synthetic-session",
    refresh_token: "synthetic-refresh",
    expires_in: 3600,
  }]);
  assert.equal(await f.auth.init(), true);
  assert.deepEqual(JSON.parse(f.calls[0].options.body), {
    auth_code: "fake-code",
    code_verifier: entry.verifier,
  });
  assert.equal(f.location.href, "https://office.example.test/pilot/");
  assert.equal(f.map.size, 1);
  f.location.href += "?code=replay";
  await assert.rejects(f.auth.init(), /expired/);
  assert.equal(f.calls.length, 1);
});
test("Apple delegates its scopes and form post to Supabase; Google keeps its identity scopes", async () => {
  for (const [provider, scopes] of [["apple", null], ["google", "openid email profile"]]) {
    const f = setup();
    await f.auth.login(provider);
    const target = new URL(f.location.next);
    assert.equal(target.origin + target.pathname, "https://project.example.test/auth/v1/authorize");
    assert.equal(target.searchParams.get("provider"), provider);
    assert.equal(target.searchParams.get("scopes"), scopes);
    assert.equal(target.searchParams.get("response_mode"), null);
    assert.equal(target.searchParams.get("code_challenge_method"), "s256");
    assert.equal(target.searchParams.get("redirect_to"), "https://office.example.test/pilot/");
  }
});
test("an unsupported provider cannot create a verifier or initiate navigation", async () => {
  const f = setup();
  for (const provider of ["unknown", "constructor"]) {
    await assert.rejects(f.auth.login(provider), /Unknown sign-in provider/);
  }
  assert.equal(f.map.size, 0);
  assert.equal(f.location.next, undefined);
});
test("ChatGPT requires an explicit opt-in and initiates identity-only custom OIDC via Supabase", async () => {
  for (const flag of [undefined, false, "true", 1]) {
    const f = setup({ chatgptSignIn: flag });
    await assert.rejects(f.auth.login("custom:chatgpt"), /Unknown sign-in provider/);
    assert.equal(f.map.size, 0);
    assert.equal(f.location.next, undefined);
  }
  const f = setup({ chatgptSignIn: true });
  await f.auth.login("custom:chatgpt");
  const target = new URL(f.location.next);
  assert.equal(target.origin + target.pathname, "https://project.example.test/auth/v1/authorize");
  assert.equal(target.searchParams.get("provider"), "custom:chatgpt");
  assert.equal(target.searchParams.get("scopes"), "openid profile email");
  assert.equal(target.searchParams.get("code_challenge_method"), "s256");
});
test("a temporarily unavailable auth service keeps the refresh grant; a revoked grant clears it", async () => {
  const f = setup(), key = "office-pilot:https://project.example.test:session";
  f.map.set(key, JSON.stringify({ access: "old", refresh: "refresh", expires: 0 }));
  f.responses.push([503, {}]);
  await assert.rejects(f.auth.request("/rest/v1/unused"), /temporarily/);
  assert.ok(f.map.has(key));
  f.responses.push([400, { error_code: "refresh_token_not_found" }]);
  await assert.rejects(f.auth.request("/rest/v1/unused"));
  assert.equal(f.map.has(key), false);
});
test("signout clears local credentials even when server revocation cannot be confirmed", async () => {
  const f = setup(), key = "office-pilot:https://project.example.test:session";
  f.map.set(key, JSON.stringify({ access: "old", refresh: "refresh", expires: 0 }));
  f.responses.push([503, {}]);
  await assert.rejects(f.auth.logout(), /revocation/);
  assert.equal(f.map.size, 0);
});
