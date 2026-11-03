const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const { webcrypto, createHash } = require("node:crypto");
const code = fs.readFileSync(path.join(__dirname, "../auth.js"), "utf8");
function setup() {
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
    window: { OFFICE_STUDIO_CONFIG: { url: "https://project.example.test", publishableKey: "public" } },
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
