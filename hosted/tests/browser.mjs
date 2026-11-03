/**
 * Browser contract test of the built hosted site, including its actual WebGL room.
 * Run with external Playwright (or PLAYWRIGHT_MODULE pointing to its installation).
 * The substituted service is loopback-only. SQL/Edge tests cover the real policies.
 */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { createServer } from "node:http";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const root = fileURLToPath(new URL("../../", import.meta.url));
const build = await mkdtemp(path.join(tmpdir(), "office-hosted-browser-"));
const origins = new Set();
const offices = new Map();
const sessions = new Map();
const codes = new Map();
const assignments = [];
const roomMessages = [];
const errors = [];
const apiKey = "sb_publishable_synthetic_fixture";
let siteOrigin,
  serviceOrigin,
  rejectFirstResult = true,
  providerCalls = 0;
const json = (res, value, status = 200) => {
  res
    .writeHead(status, { "Content-Type": "application/json" })
    .end(JSON.stringify(value));
};
async function input(req) {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  return raw ? JSON.parse(raw) : {};
}
function addOffice(owner, name, color) {
  const id = randomUUID();
  const desks = ["Head Executive", "Intake", "Legal Review"].map((name, i) => ({
    id: randomUUID(),
    name,
    position: i + 1,
    provider: "demo",
    model: "",
  }));
  offices.set(id, { id, owner, name, color, desks, files: [], runs: [] });
  return id;
}
async function stub(req, res) {
  const url = new URL(req.url, serviceOrigin);
  const query = url.searchParams;
  res.setHeader("Access-Control-Allow-Origin", siteOrigin);
  res.setHeader(
    "Access-Control-Allow-Headers",
    "authorization,apikey,content-type",
  );
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  if (req.method === "OPTIONS") return res.writeHead(204).end();
  if (url.pathname === "/auth/v1/authorize") {
    assert.equal(query.get("code_challenge_method"), "s256");
    assert.equal(query.get("redirect_to"), siteOrigin + "/");
    assert(["google", "azure"].includes(query.get("provider")));
    const code = randomUUID();
    codes.set(code, {
      owner: query.get("provider"),
      challenge: query.get("code_challenge"),
    });
    return res
      .writeHead(302, { Location: siteOrigin + "/?code=" + code })
      .end();
  }
  const body = await input(req);
  assert.equal(req.headers.apikey, apiKey);
  if (url.pathname === "/auth/v1/token") {
    assert.equal(query.get("grant_type"), "pkce");
    const record = codes.get(body.auth_code);
    assert(record, "unexpected authorization code");
    assert.equal(
      createHash("sha256").update(body.code_verifier).digest("base64url"),
      record.challenge,
    );
    codes.delete(body.auth_code);
    const token = randomUUID();
    sessions.set(token, record.owner);
    return json(res, {
      access_token: token,
      refresh_token: randomUUID(),
      expires_in: 3600,
    });
  }
  const token = (req.headers.authorization || "").slice(7);
  const user = sessions.get(token);
  if (!user) return json(res, {}, 401);
  if (url.pathname === "/auth/v1/logout") {
    sessions.delete(token);
    return res.writeHead(204).end();
  }
  if (url.pathname === "/rest/v1/office_studio_offices")
    return json(
      res,
      [...offices.values()]
        .filter((o) => o.owner === user)
        .map(({ id, name, color }) => ({ id, name, color })),
    );
  if (url.pathname === "/rest/v1/rpc/office_studio_create")
    return json(res, addOffice(user, body.p_name, body.p_color));
  const oid = body.p_office || body.office || query.get("office_id")?.slice(3);
  const office = offices.get(oid);
  if (!office || office.owner !== user) return json(res, {}, 403);
  const { desks, files, runs } = office;
  switch (url.pathname) {
    case "/rest/v1/office_studio_desks":
      return json(res, desks);
    case "/rest/v1/office_studio_files":
      if (query.get("select") === "name,content") {
        const match = files.find((f) => f.id === query.get("id")?.slice(3));
        return json(
          res,
          match ? [{ name: match.name, content: match.content }] : [],
        );
      }
      return json(
        res,
        files.map(({ id, name }) => ({ id, name })),
      );
    case "/rest/v1/office_studio_runs": {
      if (!query.has("id")) return json(res, runs);
      const result = runs.find(
        (r) => r.id === query.get("id").slice(3) && r.status === "approved",
      );
      return json(res, result ? [{ body: result.body }] : []);
    }
    case "/rest/v1/rpc/office_studio_upload":
      files.unshift({
        id: body.p_id,
        name: body.p_name,
        content: body.p_content,
      });
      return json(res, body.p_id);
    case "/rest/v1/rpc/office_studio_add_desk":
      desks.push({
        id: body.p_id,
        name: body.p_name,
        specialty: body.p_specialty,
        position: desks.length + 1,
        provider: "demo",
        model: "",
      });
      return json(res, body.p_id);
    case "/rest/v1/rpc/office_studio_decide": {
      const draft = runs.find((r) => r.id === body.p_run);
      assert.equal(draft?.status, "review");
      draft.status = body.p_decision;
      return json(res, null);
    }
    case "/rest/v1/rpc/office_studio_remove_file": {
      office.files = files.filter((f) => f.id !== body.p_file);
      office.runs = runs.filter((r) => r.file_id !== body.p_file);
      return json(res, null);
    }
    case "/functions/v1/office-drafts":
      break;
    default:
      return json(res, {}, 404);
  }
  if (body.action === "status")
    return json(res, {
      providers: [
        ["openai", "OpenAI"],
        ["anthropic", "Claude"],
        ["gemini", "Gemini"],
        ["meta", "Meta Muse"],
      ].map(([id, label]) => ({
        id,
        label,
        enabled: true,
        connected: true,
        models: ["fixture-model"],
      })),
    });
  const desk = desks.find((d) => d.id === body.desk);
  if (body.action === "route") {
    desk.provider = body.provider;
    desk.model = body.model;
    return json(res, {});
  }
  assert.equal(body.action, "draft");
  const source = files.find((file) => file.id === body.file);
  assert(source && desk);
  assignments.push(body);
  let draft = runs.find((r) => r.id === body.run);
  if (!draft) {
    assert.equal(body.provider, desk.provider);
    if (desk.provider !== "demo") {
      assert.equal(body.consent, true);
      providerCalls++;
    }
    draft = {
      id: body.run,
      desk_id: desk.id,
      file_id: source.id,
      provider: desk.provider,
      model: desk.model,
      status: "review",
      body: "Fictional draft for " + desk.name + ": " + source.content,
    };
    runs.unshift(draft);
  }
  if (rejectFirstResult) {
    rejectFirstResult = false;
    return json(
      res,
      {
        error: "The test interrupted the response. Refresh to check the draft.",
      },
      503,
    );
  }
  return json(res, { id: draft.id, status: draft.status });
}

function listen(handler) {
  const server = createServer((req, res) =>
    Promise.resolve(handler(req, res)).catch((e) => {
      errors.push(e.message);
      if (!res.headersSent) json(res, { error: "Fixture failed." }, 500);
      else res.end();
    }),
  );
  return new Promise((resolve) =>
    server.listen(0, "127.0.0.1", () => resolve(server)),
  );
}
const urlOf = (s) => "http://127.0.0.1:" + s.address().port;
const mime = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "text/javascript",
  ".txt": "text/plain",
  ".svg": "image/svg+xml",
};
let api, site, browser;
try {
  api = await listen(stub);
  serviceOrigin = urlOf(api);
  const python =
    process.env.PYTHON || (process.platform === "win32" ? "py" : "python3");
  const args = [
    ...(python === "py" ? ["-3"] : []),
    "-B",
    path.join(root, "hosted", "build_site.py"),
    "--output",
    build,
  ];
  const compiled = spawnSync(python, args, {
    encoding: "utf8",
    env: {
      ...process.env,
      SUPABASE_URL: serviceOrigin,
      SUPABASE_PUBLISHABLE_KEY: apiKey,
    },
  });
  assert.equal(compiled.status, 0, compiled.error?.message || compiled.stderr);
  site = await listen(async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    const name = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
    if (!/^[\w.-]+$/.test(name) || !mime[path.extname(name)])
      return res.writeHead(404).end();
    try {
      const data = await readFile(path.join(build, name));
      res
        .writeHead(200, { "Content-Type": mime[path.extname(name)] })
        .end(data);
    } catch {
      res.writeHead(404).end();
    }
  });
  siteOrigin = urlOf(site);
  origins.add(siteOrigin);
  origins.add(serviceOrigin);
  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_PATH || undefined,
    args: ["--enable-unsafe-swiftshader"],
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    acceptDownloads: true,
  });
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (
      ["http:", "https:"].includes(url.protocol) &&
      !origins.has(url.origin)
    ) {
      errors.push("Off-host request: " + url.origin);
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.on("pageerror", (e) => errors.push(e.message));
  await page.exposeBinding("observeRoomMessage", ({ frame }, data) => {
    if (frame.parentFrame() && data.type === "studio:room-state")
      roomMessages.push(data);
  });
  await page.addInitScript(() =>
    addEventListener("message", (event) => {
      if (window !== parent && event.data?.type === "studio:room-state")
        window.observeRoomMessage(event.data);
    }),
  );
  const el = (id) => page.locator("#" + id);
  const formButton = (id, label) =>
    el(id).getByRole("button", { name: label, exact: true });
  const waitText = async (id, expected) =>
    page.waitForFunction(
      ([id, s]) => document.getElementById(id).textContent.includes(s),
      [id, expected],
    );
  const chooseLogin = async (label) => {
    await page.getByRole("button", { name: "Continue with " + label }).click();
    await el("signed").waitFor();
    assert.equal(new URL(page.url()).search, "");
  };
  const create = async (name) => {
    await el("create").getByLabel("Business name").fill(name);
    await formButton("create", "Create office").click();
    await waitText("title", name);
    const frame = page.frameLocator("#office-room");
    await frame.locator("#rosterList li").first().waitFor({ timeout: 30000 });
    await frame.locator("canvas").first().waitFor();
    return frame;
  };
  const clear = async () => {
    await el("logout").click();
    await el("login").waitFor();
    assert.equal(await el("office-room").getAttribute("src"), null);
    assert.equal(
      await page.evaluate(() =>
        Object.keys(sessionStorage).some(
          (k) => k.endsWith(":session") || k.startsWith("office-run:"),
        ),
      ),
      false,
    );
    assert.equal(await el("offices").locator("option").count(), 0);
    assert.equal(await el("draft").locator("select option").count(), 0);
    assert.equal(await el("runs").locator(".draft-card").count(), 0);
    assert.equal(await el("destination").textContent(), "");
    assert.equal(await el("connection-status").textContent(), "");
  };
  await page.goto(siteOrigin + "/?code=unexpected");
  await waitText("notice", "expired");
  assert.equal(sessions.size, 0);
  await chooseLogin("Google");
  const room = await create("Juniper Workshop");
  const waitForFourthDesk = async () => {
    await room
      .locator("#rosterList")
      .getByText("Scheduling", { exact: true })
      .waitFor();
    assert.equal(await room.locator("#rosterList li").count(), 4);
  };
  await room
    .getByText("Ready for a file brief", { exact: true })
    .first()
    .waitFor();
  // An idle desk's walking animation must not displace its saved work status.
  const initialRoom = page
    .frames()
    .find((f) => f.url().includes("suite-room.html"));
  await initialRoom.waitForFunction(
    () => {
      const state = window.AgentOffice.state;
      return state.order.some((id) => {
        const agent = state.agents[id];
        const row = document.getElementById("r-" + id);
        const detail = row?.querySelector(".tk");
        return (
          agent.location === "walking" &&
          agent.status === "IDLE" &&
          detail?.textContent === "Ready for a file brief" &&
          row.querySelector(".chip").textContent.trim() === "Idle" &&
          detail.getBoundingClientRect().width > 0
        );
      });
    },
    null,
    { timeout: 30000 },
  );
  const boardButton = room.locator("#btnBoard");
  await boardButton.waitFor({ state: "visible" });
  await boardButton.press("Enter");
  await page.waitForFunction(() => document.activeElement?.id === "review");
  const addButton = room.locator("#btnAdd");
  await addButton.waitFor({ state: "visible" });
  await addButton.press("Enter");
  await page.waitForFunction(() => document.activeElement?.id === "desk-name");
  assert(await el("hosted-add-desk").evaluate((details) => details.open));
  await el("desk-name").fill("Scheduling");
  await el("desk-specialty").fill("Appointments");
  await formButton("add-desk", "Add desk to office").click();
  await waitForFourthDesk();
  await page.reload();
  await waitText("title", "Juniper Workshop");
  await waitForFourthDesk();
  const testSource =
    "\uFEFFSynthetic appointment inquiry for a Friday morning.\r\n";
  const fileName = "friday-inquiry.txt";
  const upload = async (buffer) => {
    await el("upload")
      .locator("input[type=file]")
      .setInputFiles({ name: fileName, mimeType: "text/plain", buffer });
    await formButton("upload", "Save file to office").click();
  };
  await upload(Buffer.from([0xc2]));
  await waitText("notice", "UTF-8");
  await upload(Buffer.from(testSource));
  await waitText("notice", "File saved");
  const originalEvent = page.waitForEvent("download");
  await el("original").click();
  const original = await originalEvent;
  assert.equal(original.suggestedFilename(), fileName);
  assert.deepEqual(
    await readFile(await original.path()),
    Buffer.from(testSource),
  );
  assert(
    (await room.locator("#rosterList").textContent()).includes("Legal Review"),
  );
  const frame = page.frames().find((f) => f.url().includes("suite-room.html"));
  assert(
    await frame.evaluate(() =>
      window.__office.renderer
        .getContext()
        .getParameter(WebGLRenderingContext.VERSION)
        .includes("WebGL"),
    ),
  );
  assert(
    await frame.evaluate(() => {
      try {
        return !parent.document;
      } catch {
        return true;
      }
    }),
    "room should have an opaque origin",
  );
  await room
    .getByText("Ready for a file brief", { exact: true })
    .first()
    .waitFor();
  const mode = page.getByRole("switch", { name: "Dark mode" });
  await mode.press("Space");
  await frame.waitForFunction(
    () => document.documentElement.dataset.appearance === "dark",
  );
  assert.equal(
    await frame.evaluate(() => window.__office.renderer.toneMappingExposure),
    0.72,
  );
  const brief = "Prepare a polite reply for owner review.";
  await el("draft")
    .locator("select[name=desk]")
    .selectOption({ label: "Intake" });
  await el("draft").getByLabel("Brief", { exact: true }).fill(brief);
  await formButton("draft", "Prepare draft").click();
  await waitText("notice", "interrupted");
  await page.reload();
  await waitText("title", "Juniper Workshop");
  await el("draft")
    .locator("select[name=desk]")
    .selectOption({ label: "Intake" });
  await el("draft").getByLabel("Brief", { exact: true }).fill(brief);
  await formButton("draft", "Prepare draft").click();
  await waitText("notice", "ready");
  assert.equal(assignments[0].run, assignments[1].run);
  assert.equal(await el("runs").locator(".draft-card").count(), 1);
  assert.equal(
    await el("runs")
      .getByRole("button", { name: "Download approved draft" })
      .count(),
    0,
  );
  assert.equal(
    await el("office-mark").getAttribute("data-waiting"),
    "false",
    "specialist draft does not signal an executive alert",
  );
  assert(
    (await room
      .locator("#rosterList")
      .getByText("Intake", { exact: true })
      .count()) > 0,
  );
  await el("runs")
    .getByRole("button", { name: "Approve", exact: true })
    .click();
  const dl = page.waitForEvent("download");
  await el("runs")
    .getByRole("button", { name: "Download approved draft" })
    .click();
  const download = await dl;
  assert.equal(download.suggestedFilename(), "approved-draft.txt");
  assert.equal(
    await readFile(await download.path(), "utf8"),
    "Fictional draft for Intake: " + testSource,
  );
  const whichOffice = await el("offices").inputValue();
  await el("connections").locator("summary").click();
  assert.deepEqual(
    await el("connect")
      .locator("select[name=provider] option")
      .allTextContents(),
    ["OpenAI", "Claude", "Gemini", "Meta Muse"],
  );
  await el("route")
    .locator("select[name=desk]")
    .selectOption({ label: "Head Executive" });
  await el("route")
    .locator("select[name=model]")
    .selectOption({ label: "OpenAI / fixture-model" });
  await formButton("route", "Save desk route").click();
  await el("draft")
    .locator("select[name=desk]")
    .selectOption({ label: "Head Executive" });
  await waitText("destination", "fixture-model");
  const consent = el("consent-label").locator("input[type=checkbox]");
  await formButton("draft", "Prepare draft").evaluate((button) =>
    button.click(),
  );
  assert.equal(providerCalls, 0);
  await consent.check();
  await el("draft")
    .getByLabel("Brief", { exact: true })
    .fill("Prepare another fictional reply.");
  assert.equal(await consent.isChecked(), false);
  await consent.check();
  await formButton("draft", "Prepare draft").click();
  await waitText("notice", "ready");
  assert.equal(providerCalls, 1);
  await page.reload();
  await waitText("title", "Juniper Workshop");
  assert.equal(await mode.getAttribute("aria-checked"), "true");
  assert.equal(await el("office-mark").getAttribute("data-waiting"), "true");
  assert.equal(
    await el("office-mark").evaluate(
      (n) => getComputedStyle(n).backgroundColor,
    ),
    "rgb(255, 114, 120)",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "phone page overflows",
  );
  if (process.env.OFFICE_STUDIO_QA_SCREENSHOT) {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page
      .frameLocator("#office-room")
      .locator("#rosterList li")
      .first()
      .waitFor();
    await el("office-room").scrollIntoViewIfNeeded();
    await page.screenshot({ path: process.env.OFFICE_STUDIO_QA_SCREENSHOT });
  }
  await el("office-mark").click();
  assert.equal(new URL(page.url()).hash, "#review");
  await el("runs")
    .getByRole("button", { name: "Decline", exact: true })
    .click();
  await waitText("notice", "Decision saved");
  assert.equal(await el("office-mark").getAttribute("data-waiting"), "false");
  assert(roomMessages.length > 0);
  for (const { office } of roomMessages) {
    assert.deepEqual(Object.keys(office).sort(), [
      "color",
      "desks",
      "name",
      "waiting",
    ]);
    for (const desk of office.desks)
      assert.deepEqual(Object.keys(desk).sort(), ["name", "specialty"]);
  }
  assert(
    !JSON.stringify(roomMessages).includes(testSource),
    "private source entered room bridge",
  );
  assert(
    !JSON.stringify(roomMessages).includes(brief),
    "private brief entered room bridge",
  );
  await clear();
  await chooseLogin("Microsoft");
  await create("Amber Studio");
  assert.notEqual(await el("offices").inputValue(), whichOffice);
  assert.equal(
    await el("draft").locator("select[name=file] option").count(),
    0,
  );
  assert.equal(await el("runs").locator(".draft-card").count(), 0);
  await clear();
  assert.equal(sessions.size, 0);
  assert.deepEqual(errors, []);
  console.log(
    "PASS Hosted Chromium " +
      browser.version() +
      " · Google/Microsoft PKCE with mocked service, real WebGL, two offices, malformed input, lost-result retry, scoped source, explicit consent, approve/download, narrow viewport, logout, zero external requests.",
  );
} finally {
  await browser?.close();
  for (const s of [api, site])
    if (s) {
      s.closeAllConnections();
      await new Promise((done) => s.close(done));
    }
  assert.equal(path.dirname(path.resolve(build)), path.resolve(tmpdir()));
  assert(path.basename(build).startsWith("office-hosted-browser-"));
  await rm(build, { recursive: true, force: true });
}
