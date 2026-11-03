"use strict";

const $ = (id) => document.getElementById(id);
const palette = {
  crimson: "#a70008",
  azure: "#2369dd",
  teal: "#16847f",
  orange: "#b87636",
  violet: "#7b46db",
  plum: "#ad4d83",
  indigo: "#5763a0",
  green: "#487445",
  lime: "#7a8e42",
};
const state = {
  workspace: null,
  workspaces: [],
  providers: [],
  epoch: 0,
  selectedId: "",
  draftId: "",
  deskKey: "",
  files: [],
  filesPhase: "idle",
  releaseFor: "",
  draftAttempt: null,
  latestDraftId: "",
  busy: false,
  template: null,
  templatePreview: null,
  templateMessage: "",
  legalTemplateRequest: null,
  templateEpoch: 0,
  logo: "",
  rooms: new Map(),
  roomFrame: null,
  roomFrameId: "",
  roomExecutivePending: false,
  addingFromRoom: false,
};
const genericPack = {
  practice: "General business",
  crew: [
    {
      name: "CRIMSON",
      specialty: "Chief of Staff",
      instruction:
        "Coordinate the crew and prepare every decision for the owner. Use placeholders only. Nothing leaves the office without owner approval.",
      color: "teal",
    },
    {
      name: "GUEST DESK",
      specialty: "Guest communications",
      instruction:
        "Prepare friendly guest communications for owner review. Use synthetic placeholders. Do not send messages or make reservations.",
      color: "azure",
    },
    {
      name: "OPERATIONS",
      specialty: "Daily operations",
      instruction:
        "Prepare checklists, schedules and operating notes for owner review. Do not change outside systems.",
      color: "green",
    },
    {
      name: "EDITOR",
      specialty: "Content drafts",
      instruction:
        "Prepare clear announcements and content for owner review. No publishing or external actions.",
      color: "orange",
    },
  ],
  gates: [
    {
      owner: "CRIMSON",
      need: "Anything sent, published, booked, purchased or changed outside this office",
      brief: {
        action:
          "Prepare a draft for the owner. Record the decision only; the owner handles any outside action.",
        ifDecline: "Keep the draft here for revision.",
      },
    },
  ],
  rules:
    "Use synthetic information and placeholders. Prepare drafts only. The owner reviews every outside action; recording approval does not perform it.",
};

function buildSyntheticPack(practice, lanes, needs) {
  const crew = [
    structuredClone(genericPack.crew[0]),
    ...lanes.map(([name, specialty, color, instruction]) => ({
      name,
      specialty,
      color,
      instruction:
        instruction +
        " Use synthetic placeholders only. Prepare drafts for owner review; do not take external actions.",
    })),
  ];
  return {
    practice,
    crew,
    gates: needs.map((need) => ({
      owner: "CRIMSON",
      need,
      brief: {
        action:
          "Prepare an administrative draft for the owner. Record the decision only; the owner carries out any next step.",
        ifDecline: "Keep the draft here for revision.",
      },
    })),
    rules:
      "Synthetic planning and administrative support only. Qualified owners review scientific, regulatory, product and spending decisions. No clinical decisions, experimental procedures, system changes, submissions or external communications are performed by this office.",
  };
}
const localTemplates = {
  generic: genericPack,
  research: buildSyntheticPack(
    "Scientific research",
    [
      [
        "LITERATURE",
        "Literature & source review",
        "azure",
        "Prepare a source-review outline and identify evidence gaps; do not invent findings or citations.",
      ],
      [
        "PLANNING",
        "Research planning support",
        "teal",
        "Draft high-level planning questions and review checklists without experimental procedures.",
      ],
      [
        "EVIDENCE",
        "Evidence register",
        "green",
        "Organize synthetic evidence-register headings and provenance questions for owner review.",
      ],
      [
        "GRANTS",
        "Grant administration",
        "orange",
        "Prepare a grant checklist and draft administrative milestones without submitting anything.",
      ],
      [
        "EDITOR",
        "Research communication",
        "plum",
        "Draft a clearly qualified research summary using supplied synthetic material; flag unverified claims.",
      ],
    ],
    [
      "Scientific claims and research-direction decisions: qualified owner only",
      "Any publication, submission or external message: owner approval required",
      "Any spending or data-access change: owner decision only",
    ],
  ),
  biotech: buildSyntheticPack(
    "Biotech",
    [
      [
        "EVIDENCE",
        "Evidence & provenance",
        "azure",
        "Prepare a synthetic evidence inventory and mark unsupported statements for review.",
      ],
      [
        "PROGRAMS",
        "Program coordination",
        "teal",
        "Draft a program-status outline and administrative handoff checklist.",
      ],
      [
        "QUALITY",
        "Quality documentation",
        "green",
        "Prepare document-control checklists and identify missing administrative records without certifying compliance.",
      ],
      [
        "REGULATORY",
        "Regulatory research support",
        "indigo",
        "Draft source questions and review checklists; do not give a regulatory determination or file submissions.",
      ],
      [
        "PARTNERS",
        "Partner communications",
        "plum",
        "Prepare a partner-update draft from synthetic placeholders without making product claims.",
      ],
    ],
    [
      "Scientific, regulatory and product decisions: qualified owner only",
      "Any external communication or submission: owner approval required",
      "Any spending, commitment or system change: owner decision only",
    ],
  ),
};
function executiveAgent(office = state.workspace) {
  const crew = office?.crew || [];
  return crew.find((agent) => agent.name === "CRIMSON") ||
    crew.find((agent) => agent.specialty === "Chief of Staff") || crew[0];
}
function isChief(agent, office = state.workspace) {
  return !!agent && agent.name === executiveAgent(office)?.name;
}
function defaultAgentTitle(agent) {
  return isChief(agent)
    ? "Head Executive"
    : agent?.specialty || agent?.name || "Agent";
}
function agentAppearance(agent) {
  return agent?.appearance || {};
}
function displayAgentTitle(agent) {
  return (
    agentAppearance(agent).title ||
    agent?.displayTitle ||
    agent?.title ||
    defaultAgentTitle(agent)
  );
}
function defaultAgentColor(agent, workspace = state.workspace) {
  if (isChief(agent, workspace)) return safeColor(workspace?.color);
  return (
    palette[agent?.color] ||
    (/^#[a-f\d]{6}$/i.test(agent?.color || "")
      ? agent.color
      : safeColor(workspace?.color))
  );
}
function displayAgentColor(agent, workspace = state.workspace) {
  const color = agentAppearance(agent).color;
  return /^#[a-f\d]{6}$/i.test(color || "")
    ? color
    : defaultAgentColor(agent, workspace);
}
function agentDisplayLabel(name) {
  const agent = state.workspace?.crew.find((item) => item.name === name);
  return agent ? displayAgentTitle(agent) + " (" + name + ")" : name;
}
function renderAgentAppearance() {
  const agent = selectedAgent();
  const appearance = agentAppearance(agent);
  $("appearance-title").value =
    appearance.title || agent?.displayTitle || agent?.title || "";
  $("appearance-title").placeholder = defaultAgentTitle(agent);
  $("appearance-color").value = displayAgentColor(agent);
  $("appearance-default-color").checked = !appearance.color;
  $("appearance-color").disabled = !appearance.color;
  $("appearance-default-note").textContent =
    "Default: " +
    defaultAgentTitle(agent) +
    " · " +
    defaultAgentColor(agent) +
    (isChief(agent) && validLogo(state.workspace?.logo)
      ? " · Office Suite logo avatar"
      : "");
  $("save-appearance").disabled = state.busy || !agent;
  $("reset-appearance").disabled = state.busy || !agent;
}

async function api(path, body) {
  const response = await fetch(
    path,
    body === undefined
      ? { cache: "no-store" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("The local server returned an unreadable response.");
  }
  if (!response.ok) {
    const error = new Error(
      typeof result.error === "string"
        ? result.error
        : "The local server could not complete this request.",
    );
    error.code = result.code;
    throw error;
  }
  return result;
}
function notice(message, error = false) {
  const box = $("notice");
  box.textContent = message;
  box.classList.toggle("error", error);
  box.hidden = !message;
}
function el(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = String(text);
  return item;
}
function option(value, label, disabled = false) {
  const item = el("option", "", label);
  item.value = value;
  item.disabled = disabled;
  return item;
}
function isCurrent(id, epoch) {
  // A response belongs to the workspace selection that started its request.
  // Selecting another office invalidates outstanding reads and mutations.
  return state.selectedId === id && state.epoch === epoch;
}
function safeColor(value) {
  return /^#[a-f\d]{6}$/i.test(value || "") ? value : "#000000";
}
function applyAccent(value) {
  const color = safeColor(value);
  document.documentElement.style.setProperty("--accent", color);
  const rgb = color
    .slice(1)
    .match(/../g)
    .map((x) => parseInt(x, 16) / 255)
    .map((x) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
  const luminance = rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  document.documentElement.style.setProperty(
    "--accent-ink",
    luminance > 0.179 ? "#000000" : "#ffffff",
  );
}
function resetWorkspaceForms() {
  state.addingFromRoom = false;
  state.files = [];
  state.filesPhase = "idle";
  state.releaseFor = "";
  state.draftAttempt = null;
  state.latestDraftId = "";
  $("review-latest").hidden = true;
  $("reset-attempt").hidden = true;
  $("draft-feedback").textContent = "";
  $("file-status").textContent = "";
  $("add-file").value = "";
  $("share-file").checked = false;
  renderFileLibrary("");
  $("draft-brief").value = "";
  $("draft-provider").value = "route";
  state.deskKey = "";
  $("add-agent-form").reset();
  $("add-agent-form").hidden = true;
  $("show-add-agent").hidden = false;
}
function updatePracticeLabel() {
  const general = $("practice").value === "generic";
  $("practice-label-field").hidden = !general;
  $("practice-label").required = general;
}
function validLogo(value) {
  return (
    typeof value === "string" &&
    /^data:image\/(png|jpeg|webp);base64,[a-z\d+/=]+$/i.test(value) &&
    value.length < 280000
  );
}
function setBusy(value) {
  state.busy = value;
  $("generate-draft").disabled = value;
  $("approve-draft").disabled = value;
  $("decline-draft").disabled = value;
  $("draft-provider").disabled = value;
  $("draft-agent").disabled = value;
  $("draft-brief").disabled = value;
  $("add-file").disabled = value || state.filesPhase !== "ready";
  $("draft-file").disabled = value || state.filesPhase !== "ready";
  $("delete-file").disabled = value;
  $("add-agent-form").querySelector("button[type=submit]").disabled = value;
  $("generate-draft").firstChild.textContent = value
    ? "Please wait…"
    : "Prepare draft ";
  updateProviderNote();
  $("save-appearance").disabled = value || !selectedAgent();
  $("reset-appearance").disabled = value || !selectedAgent();
  $("save-manual").disabled = value || !state.workspace;
  if (state.workspace) renderRouteModels($("route-model").value);
}
function renderSelector() {
  const select = $("workspace-select");
  select.replaceChildren(option("", "Choose an Office Suite"));
  for (const office of state.workspaces)
    select.append(option(office.id, office.name));
  select.value = state.selectedId;
}
function registerWorkspace(workspace) {
  const existing = state.workspaces.findIndex(
    (item) => item.id === workspace.id,
  );
  const summary = { id: workspace.id, name: workspace.name };
  if (existing < 0) state.workspaces.push(summary);
  else state.workspaces[existing] = summary;
  renderSelector();
}
function renderTemplate() {
  const box = $("template-preview");
  box.replaceChildren();
  const pack = state.template || state.templatePreview;
  if (!pack) {
    box.append(
      el(
        "strong",
        "",
        state.templateMessage
          ? "Template unavailable"
          : "Loading the template…",
      ),
      el(
        "p",
        "",
        state.templateMessage ||
          "Preparing the crew, dedicated LEGAL desk and approval gates.",
      ),
    );
    return;
  }
  box.append(
    el(
      "strong",
      "",
      state.templateMessage
        ? pack.crew.length + " supplied desks · LEGAL needs one free seat"
        : pack.crew.length +
            " desks · LEGAL included · " +
            pack.gates.length +
            " approval gate" +
            (pack.gates.length === 1 ? "" : "s"),
    ),
    el("p", "", pack.crew.map((agent) => agent.name).join(" / ")),
  );
  if (state.templateMessage) box.append(el("p", "", state.templateMessage));
}
function templateFailure(error) {
  state.template = null;
  state.templatePreview = error.preview || null;
  state.templateMessage =
    error instanceof SyntaxError
      ? "This file is not valid JSON."
      : error.message;
  renderTemplate();
  notice(state.templateMessage, true);
}
async function legalDeskTemplate() {
  if (!state.legalTemplateRequest) {
    state.legalTemplateRequest = api("/api/templates/legal")
      .then((source) => {
        const agent = {};
        for (const key of [
          "name",
          "specialty",
          "engine",
          "color",
          "style",
          "systems",
          "instruction",
        ]) {
          if (Object.prototype.hasOwnProperty.call(source, key))
            agent[key] = structuredClone(source[key]);
        }
        checkedPack({ crew: [agent], gates: [], rules: "" });
        if (agent.name !== "LEGAL")
          throw new Error(
            "The local server did not provide its LEGAL desk template. Restart the updated server and try again.",
          );
        return agent;
      })
      .catch((error) => {
        state.legalTemplateRequest = null;
        throw error;
      });
  }
  return state.legalTemplateRequest;
}
async function prepareSetupPack(source) {
  const pack = checkedPack(source);
  if (pack.crew.some((agent) => agent.name.trim().toLowerCase() === "legal"))
    return pack;
  if (pack.crew.length >= 10) {
    const error = new Error(
      "The 10-desk limit includes LEGAL. Remove one desk from your imported JSON and import it again, or choose another template. No desks were removed automatically.",
    );
    error.preview = pack;
    throw error;
  }
  const legal = await legalDeskTemplate();
  return { ...pack, crew: [...pack.crew, structuredClone(legal)] };
}
function checkedPack(pack) {
  if (
    !pack ||
    typeof pack !== "object" ||
    !Array.isArray(pack.crew) ||
    !pack.crew.length ||
    pack.crew.length > 10 ||
    !Array.isArray(pack.gates) ||
    typeof pack.rules !== "string"
  )
    throw new Error(
      "Choose an intake pack with 1–10 agents, approval gates, and office rules.",
    );
  const seen = new Set();
  for (const agent of pack.crew) {
    if (
      !agent ||
      typeof agent.name !== "string" ||
      !agent.name.trim() ||
      agent.name.length > 14 ||
      typeof agent.specialty !== "string" ||
      typeof agent.instruction !== "string" ||
      seen.has(agent.name.trim().toLowerCase())
    )
      throw new Error(
        "Each agent needs a unique name (up to 14 characters), specialty, and instruction.",
      );
    seen.add(agent.name.trim().toLowerCase());
  }
  for (const gate of pack.gates) {
    if (
      !gate ||
      typeof gate.owner !== "string" ||
      typeof gate.need !== "string"
    )
      throw new Error("Each approval gate needs an owner and a need.");
  }
  return pack;
}
async function loadTemplate() {
  const epoch = ++state.templateEpoch;
  state.template = null;
  state.templatePreview = null;
  state.templateMessage = "";
  $("create-office").disabled = true;
  renderTemplate();
  try {
    const key = $("practice").value;
    const pack = localTemplates[key]
      ? structuredClone(localTemplates[key])
      : await api(`/packs/${encodeURIComponent(key)}.json`);
    if (epoch !== state.templateEpoch) return;
    const prepared = await prepareSetupPack(pack);
    if (epoch !== state.templateEpoch) return;
    state.template = prepared;
    renderTemplate();
  } catch (error) {
    if (epoch !== state.templateEpoch) return;
    templateFailure(error);
  } finally {
    if (epoch === state.templateEpoch)
      $("create-office").disabled = !state.template;
  }
}
function showSetup() {
  document.body.classList.remove("room-full-window");
  releaseRoomFrame();
  resetWorkspaceForms();
  $("office-form").reset();
  clearLogo();
  updatePracticeLabel();
  loadTemplate();
  history.replaceState(null, "", location.pathname);
  ++state.epoch;
  state.selectedId = "";
  state.workspace = null;
  updateReviewMark(0);
  setBusy(false);
  renderSelector();
  $("setup").hidden = false;
  $("workspace").hidden = true;
  applyAccent($("office-color").value);
  notice("");
  $("office-name").focus();
}
async function selectWorkspace(id) {
  if (!id) {
    showSetup();
    return;
  }
  const epoch = ++state.epoch;
  if (state.selectedId !== id) releaseRoomFrame();
  resetWorkspaceForms();
  state.selectedId = id;
  state.workspace = null;
  updateReviewMark(0);
  state.draftId = "";
  setBusy(false);
  renderSelector();
  $("setup").hidden = true;
  $("workspace").hidden = true;
  notice("Opening your office…");
  try {
    const workspace = await api(`/api/workspaces/${encodeURIComponent(id)}`);
    if (!isCurrent(id, epoch)) return;
    state.workspace = workspace;
    notice("");
    renderWorkspace();
  } catch (error) {
    if (isCurrent(id, epoch)) {
      notice(error.message, true);
      $("setup").hidden = false;
    }
  }
}
function selectedAgent() {
  return state.workspace?.crew.find(
    (agent) => agent.name === $("draft-agent").value,
  );
}
function savedRoute(agent = selectedAgent()) {
  return agent?.routing || { provider: "demo", model: "" };
}
function providerModels(provider) {
  return Array.isArray(provider?.models)
    ? provider.models.filter((model) => typeof model === "string" && model)
    : [];
}
function providerLabel(id) {
  return state.providers.find((provider) => provider.id === id)?.label || id;
}
function canSaveRoute(provider, model) {
  return provider?.id === "demo" || providerModels(provider).includes(model);
}
function routeInfo(route) {
  const provider = state.providers.find((item) => item.id === route.provider);
  if (route.provider === "demo")
    return {
      provider,
      model: "",
      available: !!provider?.configured,
      label: "Local demo · simulated",
    };
  const models = providerModels(provider);
  const model = route.model || models[0] || "";
  const available = !!provider?.configured && models.includes(model);
  return {
    provider,
    model,
    available,
    label:
      providerLabel(route.provider) +
      (model ? " / " + model : " / no model configured"),
  };
}
function renderProviders() {
  const select = $("route-provider");
  select.replaceChildren();
  const rank = { demo: 0, openai: 1, anthropic: 2, gemini: 3, meta: 4 };
  for (const provider of [...state.providers].sort(
    (a, b) => (rank[a.id] ?? 9) - (rank[b.id] ?? 9),
  )) {
    select.append(
      option(
        provider.id,
        provider.id === "demo"
          ? "Local demo · simulated"
          : provider.label +
              (provider.configured
                ? " · configured on host"
                : " · not configured"),
        provider.id !== "demo" && !providerModels(provider).length,
      ),
    );
  }
  const draftSelect = $("draft-provider");
  const previous = draftSelect.value;
  draftSelect.replaceChildren(
    option("route", "Use saved desk route"),
    option("demo", "Local demo · this draft only"),
  );
  draftSelect.value = previous === "demo" ? "demo" : "route";
  if (state.workspace) updateAgent();
  else updateProviderNote();
}
function renderRouteModels(preferred = "") {
  const provider = state.providers.find(
    (item) => item.id === $("route-provider").value,
  );
  const select = $("route-model");
  select.replaceChildren();
  if (provider?.id === "demo") {
    select.append(option("", "No model · simulated locally"));
    select.disabled = true;
  } else {
    const models = providerModels(provider);
    for (const model of models) select.append(option(model, model));
    if (preferred && !models.includes(preferred))
      select.append(option(preferred, preferred + " · unavailable", true));
    if (!models.length && !preferred)
      select.append(option("", "No host-allowed models", true));
    select.value = preferred || models[0] || "";
    select.disabled = !models.length;
  }
  const valid = canSaveRoute(provider, select.value);
  $("save-route").disabled = state.busy || !selectedAgent() || !valid;
  $("route-status").textContent =
    provider?.id === "demo"
      ? "Local demo uses no model connection or credentials."
      : provider?.configured
        ? "Configured on this host. This status does not test credentials or model access."
        : providerModels(provider).length
          ? "You can save a model preference now. Live drafting requires a provider key on this computer."
          : "Add an allowed model on the host to save this provider.";
}
function renderDeskSettings() {
  const agent = selectedAgent();
  const route = savedRoute(agent);
  const info = routeInfo(route);
  $("route-agent").textContent = agent
    ? "Saved preference for " +
      agent.name +
      ". Applies to future drafts from this desk."
    : "Choose a desk first.";
  $("saved-route-label").textContent =
    info.label + (info.available ? "" : " · unavailable");
  const select = $("route-provider");
  if (!state.providers.some((provider) => provider.id === route.provider))
    select.append(
      option(route.provider, route.provider + " · unavailable", true),
    );
  select.value = route.provider;
  renderRouteModels(route.model || "");
}
function officePath(id, suffix) {
  return "/api/workspaces/" + encodeURIComponent(id) + suffix;
}
function selectedFile() {
  return state.files.find((file) => file.id === $("draft-file").value);
}
// Retain only a fingerprint and request token for an interrupted submission.
// The selected original and brief stay out of browser storage.
async function fileAttempt(id, epoch, body) {
  const key = "office-studio:file-draft:" + id;
  const bytes = new TextEncoder().encode(JSON.stringify(body));
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  if (!isCurrent(id, epoch)) return null;
  const signature = Array.from(new Uint8Array(hash), (n) => n.toString(16).padStart(2, "0")).join("");
  let previous = state.draftAttempt;
  if (!previous) {
    try { previous = JSON.parse(sessionStorage.getItem(key)); } catch { /* Session storage is optional. */ }
  }
  const token = previous?.signature === signature && typeof previous.id === "string"
    ? previous.id : crypto.randomUUID();
  state.draftAttempt = {signature, id: token};
  try { sessionStorage.setItem(key, JSON.stringify(state.draftAttempt)); } catch { /* In-memory retry. */ }
  return token;
}
function forgetFileAttempt() {
  state.draftAttempt = null;
  try { sessionStorage.removeItem("office-studio:file-draft:" + state.selectedId); } catch { /* In-memory retry. */ }
}
function fileLabel(file) {
  return file.name + " · " + file.version.slice(0, 8);
}
function renderFileLibrary(selectId = $("draft-file").value) {
  const select = $("draft-file");
  select.replaceChildren(option("", "Brief only"));
  for (const file of state.files) select.append(option(file.id, fileLabel(file)));
  select.value = state.files.some((file) => file.id === selectId) ? selectId : "";
  $("saved-file-field").hidden = !state.files.length;
  select.disabled = state.busy || state.filesPhase !== "ready";
  $("add-file").disabled = select.disabled;
  $("reload-files").hidden = state.filesPhase !== "error";
  const file = selectedFile();
  $("file-tools").hidden = !file;
  $("file-delete-options").open = false;
  const original = $("original-download");
  if (file) original.href = officePath(state.selectedId, "/files/" + encodeURIComponent(file.id) + "/download");
  else original.removeAttribute("href");
  updateProviderNote();
}
async function loadFiles() {
  if (!state.workspace || state.filesPhase === "loading") return;
  const id = state.selectedId, epoch = state.epoch;
  state.filesPhase = "loading";
  renderFileLibrary();
  try {
    const result = await api(officePath(id, "/files"));
    if (!isCurrent(id, epoch)) return;
    state.files = result.files;
    state.filesPhase = "ready";
    $("file-status").textContent = "";
  } catch {
    if (!isCurrent(id, epoch)) return;
    state.filesPhase = "error";
    $("file-status").textContent = "The saved files could not be loaded.";
  }
  renderFileLibrary();
}
async function addWorkingFile() {
  const input = $("add-file");
  const file = input.files[0];
  if (!file || state.busy || !state.workspace) return;
  const id = state.selectedId, epoch = state.epoch;
  renderFileLibrary("");
  setBusy(true);
  $("file-status").textContent = "Saving the original in this office…";
  try {
    if (!/\.(txt|md)$/i.test(file.name) || !file.size || file.size > 32768)
      throw new Error("Choose a nonempty .txt or .md file up to 32 KB.");
    const bytes = await file.arrayBuffer();
    if (!isCurrent(id, epoch)) return;
    let content;
    try {
      content = new TextDecoder("utf-8", {fatal: true, ignoreBOM: true}).decode(bytes);
    } catch {
      throw new Error("Save this file as UTF-8 plain text and choose it again.");
    }
    const result = await api(officePath(id, "/files"), {name: file.name, content});
    if (!isCurrent(id, epoch)) return;
    state.files = [result.file, ...state.files.filter((item) => item.id !== result.file.id)];
    renderFileLibrary(result.file.id);
    $("file-status").textContent = "Saved and selected: " + result.file.name;
  } catch (error) {
    if (isCurrent(id, epoch)) $("file-status").textContent = error.message;
  } finally {
    if (isCurrent(id, epoch)) {
      input.value = "";
      setBusy(false);
    }
  }
}
async function removeWorkingFile() {
  const file = selectedFile();
  if (!file || state.busy || !state.workspace) return;
  const id = state.selectedId, epoch = state.epoch;
  setBusy(true);
  try {
    const result = await api(officePath(id, "/files/" + encodeURIComponent(file.id) + "/delete"), {});
    if (!isCurrent(id, epoch)) return;
    state.files = result.files;
    renderFileLibrary("");
    $("file-status").textContent = "Removed from this office: " + file.name;
  } catch (error) {
    if (isCurrent(id, epoch)) $("file-status").textContent = error.message;
  } finally {
    if (isCurrent(id, epoch)) {
      setBusy(false);
      if (!selectedFile()) (state.files.length ? $("draft-file") : $("add-file")).focus();
    }
  }
}
function updateProviderNote() {
  const override = $("draft-provider").value === "demo";
  const info = routeInfo(
    override ? { provider: "demo", model: "" } : savedRoute(),
  );
  $("provider-note").textContent = !info.available
    ? "This desk’s saved route is unavailable. Choose Local demo for this draft or update Desk settings; no live fallback will be used."
    : info.provider?.id === "demo"
      ? override
        ? "Temporary Local demo override. The saved desk route stays unchanged."
        : "Saved route: Local demo. Simulated output; no model connection is used."
      : "Saved route: " +
        info.label +
        ". This provider receives the brief, the selected agent’s instructions and office rules. Host configuration does not verify account access.";
  const file = selectedFile();
  const desk = selectedAgent();
  const live = !!file && !!desk && info.available && info.provider?.id !== "demo";
  const scope = live ? JSON.stringify([state.selectedId, file.id, file.version, desk.name, info.provider.id, info.model]) : "";
  if (scope !== state.releaseFor) {
    $("share-file").checked = false;
    state.releaseFor = scope;
  }
  $("file-release").hidden = !live;
  $("share-file").required = live;
  $("share-file").disabled = state.busy || !live;
  if (live) $("file-release-label").textContent =
    "Allow " + displayAgentTitle(desk) + " to share “" + file.name + "” with " + info.label + " for this draft.";
  if (file && !live && info.provider?.id === "demo")
    $("provider-note").textContent = "Local demo prepares a sample on this computer using “" + file.name + "”.";
  $("generate-draft").disabled = state.busy || !desk || !info.available || (live && !$("share-file").checked);
}
function updateAgent() {
  const name = $("draft-agent").value;
  const agent = selectedAgent();
  const key = state.selectedId + ":" + name;
  if (state.deskKey !== key) {
    state.deskKey = key;
    $("draft-provider").value = "route";
  }
  $("agent-description").textContent = agent
    ? agent.name + " · " + agent.specialty
    : "";
  for (const button of $("desks").children)
    button.setAttribute("aria-pressed", String(button.dataset.agent === name));
  renderDeskSettings();
  renderAgentAppearance();
  updateProviderNote();
}
function draftRouteLabel(draft) {
  return draft.provider === "demo"
    ? "Local demo · simulated"
    : providerLabel(draft.provider) +
        (draft.model ? " / " + draft.model : " / model not recorded");
}
function manualURL(value) {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    const url = new URL(trimmed);
    return url.protocol === "https:" &&
      url.hostname &&
      !url.username &&
      !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}
function renderManual(workspace) {
  const url = manualURL(workspace.manualUrl || "");
  $("save-manual").disabled = state.busy;
  $("manual-url").value = url || "";
  $("manual-open").hidden = !url;
  if (url) $("manual-open").href = url;
  else $("manual-open").removeAttribute("href");
}
function roomSignature(workspace) {
  return JSON.stringify([
    workspace.name,
    workspace.town,
    workspace.color,
    workspace.logo,
    workspace.crew.map((agent) => [
      agent.name,
      agent.specialty,
      agent.color,
      agent.style,
      displayAgentTitle(agent),
      displayAgentColor(agent, workspace),
    ]),
  ]);
}
function localRoomURL(value) {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" &&
      ["127.0.0.1", "localhost"].includes(url.hostname) &&
      url.hostname === location.hostname &&
      url.origin !== location.origin &&
      !url.username &&
      !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}
function displayOfficeView(entry) {
  const ready = !!entry?.url;
  const showRoom = entry?.view === "room" && (ready || entry.pending);
  const fullWindow = new URLSearchParams(location.search).get("view") === "room";
  document.body.classList.toggle("room-full-window", fullWindow && showRoom);
  $("view-room").disabled = !ready;
  $("view-room").setAttribute("aria-pressed", String(showRoom));
  $("view-desks").setAttribute("aria-pressed", String(!showRoom));
  $("room-stage").hidden = !showRoom;
  $("desk-workspace").hidden = showRoom;
  const fullLink = $("room-full-tab");
  fullLink.hidden = !ready;
  if (ready) {
    const url = new URL(location.pathname, location.origin);
    if (!fullWindow) url.searchParams.set("view", "room");
    url.hash = "office/" + state.selectedId;
    fullLink.href = url.href;
    fullLink.target = fullWindow ? "_self" : "_blank";
    fullLink.textContent = fullWindow ? "Back to workspace" : "Open room in full tab ↗";
  } else fullLink.removeAttribute("href");
  $("room-availability").textContent = entry?.pending
    ? "Opening your office…"
    : ready
      ? "3D office · simulated activity"
      : "The room could not open. You can still use Desks & drafts.";
  for (const frame of $("room-frames").children)
    frame.hidden = frame !== entry?.frame;
}
function chooseOfficeView(view) {
  const entry = state.rooms.get(state.selectedId);
  if (!entry || (view === "room" && !entry.url)) return;
  entry.view = view;
  entry.userChoice = true;
  displayOfficeView(entry);
}
function currentAppearance() {
  return document.documentElement.dataset.appearance === "dark" ? "dark" : "light";
}
function syncRoomAppearance() {
  postToRoom({type: "office-studio:appearance", mode: currentAppearance()});
}
window.addEventListener("office-studio:appearance", syncRoomAppearance);
function releaseRoomFrame() {
  if (!state.roomFrameId) return;
  const entry = state.rooms.get(state.roomFrameId);
  if (entry) entry.frame = null;
  // A new browsing context also rejects late messages from the retired room.
  state.roomFrame.remove();
  state.roomFrame = null;
  state.roomFrameId = "";
  state.roomExecutivePending = false;
  updateReviewMark();
}
function ensureRoomFrame(entry, workspace, reload) {
  if (state.roomFrame && (reload || state.roomFrameId !== workspace.id))
    releaseRoomFrame();
  if (!state.roomFrame) {
    const frame = el("iframe", "embedded-room");
    frame.setAttribute(
      "sandbox",
      "allow-scripts allow-same-origin allow-pointer-lock",
    );
    frame.setAttribute("referrerpolicy", "no-referrer");
    frame.setAttribute("allow", "screen-wake-lock; fullscreen");
    frame.addEventListener("load", syncRoomReviewSignal);
    frame.addEventListener("load", syncRoomAppearance);
    frame.setAttribute("aria-describedby", "room-disclosure");
    frame.addEventListener("error", () => {
      const current = state.rooms.get(state.roomFrameId);
      if (frame !== state.roomFrame || !current || !isCurrent(state.roomFrameId, current.epoch)) return;
      current.url = null;
      current.view = "desks";
      releaseRoomFrame();
      displayOfficeView(current);
    });
    state.roomFrame = frame;
    $("room-frames").append(frame);
  }
  state.roomFrameId = workspace.id;
  entry.frame = state.roomFrame;
  entry.frame.title = workspace.name + " · simulated 3D office";
  if (entry.frame.dataset.roomUrl !== entry.url) {
    const initial = new URL(entry.url);
    initial.searchParams.set("appearance", currentAppearance());
    entry.frame.dataset.roomUrl = entry.url;
    entry.frame.src = initial.href;
  }
}
function syncOfficeRoom() {
  const workspace = state.workspace;
  if (!workspace) return;
  const id = workspace.id,
    epoch = state.epoch,
    signature = roomSignature(workspace);
  let entry = state.rooms.get(id);
  if (entry && entry.signature === signature) {
    entry.epoch = epoch;
    if (entry.url && !entry.pending) ensureRoomFrame(entry, workspace, false);
    displayOfficeView(entry);
    if (entry.pending && entry.requestEpoch !== epoch)
      requestOfficeRoom(entry, workspace, epoch, false);
    return;
  }
  const reload = !!entry?.frame;
  if (!entry)
    entry = {
      view: "room",
      userChoice: false,
      url: null,
      frame: null,
      request: 0,
    };
  entry.signature = signature;
  entry.epoch = epoch;
  entry.pending = true;
  state.rooms.set(id, entry);
  displayOfficeView(entry);
  requestOfficeRoom(entry, workspace, epoch, reload);
}
async function requestOfficeRoom(entry, workspace, epoch, reload) {
  const id = workspace.id,
    request = ++entry.request;
  entry.requestEpoch = epoch;
  try {
    const result = await api(
      "/api/workspaces/" + encodeURIComponent(id) + "/room",
    );
    if (entry.request !== request || state.rooms.get(id) !== entry) return;
    entry.url = localRoomURL(result.url);
    entry.pending = false;
    if (entry.url && !entry.userChoice) entry.view = "room";
    if (!isCurrent(id, epoch)) return;
    if (entry.url) ensureRoomFrame(entry, workspace, reload);
    displayOfficeView(entry);
  } catch {
    if (entry.request !== request || state.rooms.get(id) !== entry) return;
    entry.pending = false;
    entry.url = null;
    entry.view = "desks";
    if (isCurrent(id, epoch)) displayOfficeView(entry);
  }
}

function renderWorkspace() {
  const workspace = state.workspace;
  if (!workspace) return;
  if (state.filesPhase === "idle") loadFiles();
  history.replaceState(null, "", "#office/" + workspace.id);
  $("setup").hidden = true;
  $("workspace").hidden = false;
  applyAccent(workspace.color);
  $("workspace-title").textContent = workspace.name;
  $("room-title").textContent = workspace.name;
  $("workspace-town").textContent =
    workspace.town || "Your local working space";
  $("town-map").hidden = !workspace.town;
  $("map-note").hidden = !workspace.town;
  if (workspace.town)
    $("town-map").href =
      "https://www.openstreetmap.org/search?query=" +
      encodeURIComponent(workspace.town);
  else $("town-map").removeAttribute("href");
  const logo = $("workspace-logo");
  logo.hidden = !validLogo(workspace.logo);
  if (!logo.hidden) {
    logo.src = workspace.logo;
    logo.alt = workspace.name + " logo";
  } else logo.removeAttribute("src");
  const previous = $("draft-agent").value;
  $("draft-agent").replaceChildren();
  $("desks").replaceChildren();
  workspace.crew.forEach((agent, index) => {
    const desk = el("button", "desk");
    desk.type = "button";
    desk.dataset.agent = agent.name;
    desk.setAttribute(
      "aria-label",
      `${displayAgentTitle(agent)}, ${agent.name}, ${agent.specialty}. Prepare a brief.`,
    );
    desk.style.setProperty("--desk-color", displayAgentColor(agent, workspace));
    const avatar = el("span", "desk-avatar");
    if (isChief(agent) && validLogo(workspace.logo)) {
      avatar.classList.add("has-logo");
      const image = el("img");
      image.src = workspace.logo;
      image.alt = "";
      avatar.append(image);
    }
    desk.append(
      avatar,
      el("strong", "", displayAgentTitle(agent)),
      el("small", "", agent.name),
    );
    desk.addEventListener("click", () => {
      $("draft-agent").value = agent.name;
      updateAgent();
      $("draft-brief").focus();
    });
    $("desks").append(desk);
    $("draft-agent").append(
      option(agent.name, `${displayAgentTitle(agent)} · ${agent.name}`),
    );
  });
  if (workspace.crew.some((a) => a.name === previous))
    $("draft-agent").value = previous;
  updateAgent();
  $("crew-count").textContent = `${workspace.crew.length} / 10 seats`;
  $("show-add-agent").disabled = workspace.crew.length >= 10;
  $("show-add-agent").textContent =
    workspace.crew.length >= 10 ? "All ten desks are taken" : "+ Add a desk";
  $("office-rules").textContent = workspace.rules || "";
  $("office-gates").replaceChildren();
  for (const gate of workspace.gates || [])
    $("office-gates").append(
      el("li", "", `${agentDisplayLabel(gate.owner)} · ${gate.need}`),
    );
  renderDrafts();
  renderManual(workspace);
  syncOfficeRoom();
}
function postToRoom(message) {
  const frame = state.roomFrame,
    office = state.workspace;
  if (
    !office ||
    state.roomFrameId !== office.id ||
    !frame?.contentWindow ||
    !localRoomURL(frame.src)
  )
    return;
  frame.contentWindow.postMessage(message, new URL(frame.src).origin);
}
function syncRoomReviewSignal() {
  const office = state.workspace;
  if (office) postToRoom({
    type: "office-studio:review-signal",
    pending: office.drafts.some((draft) => draft.status === "pending"),
    executivePending: !!pendingExecutiveDraft(office),
  });
}

function pendingExecutiveDraft(office) {
  const executive = executiveAgent(office);
  return executive && office.drafts.find(
    (draft) => draft.status === "pending" && draft.agent === executive.name,
  );
}

function updateReviewMark(pending = state.workspace?.drafts.filter(draft => draft.status === "pending").length || 0) {
  const mark = $("review-mark");
  const saved = pendingExecutiveDraft(state.workspace);
  const native = !!state.workspace && state.roomExecutivePending;
  mark.disabled = !state.workspace;
  mark.dataset.pending = String(pending);
  mark.dataset.active = String(pending > 0 || native);
  mark.dataset.executiveAlert = String(!!saved || native);
  let label = "Beyder & Co. ampersand";
  if (state.workspace) {
    const executive = displayAgentTitle(executiveAgent());
    if (saved) label += ` · Review ${executive}’s draft in the approval inbox`;
    else if (native) label += ` · Open ${executive}’s approval in the 3D office`;
    else label += ` · Open approval inbox · ${pending} pending draft${pending === 1 ? "" : "s"}`;
  }
  mark.setAttribute("aria-label", label);
  mark.title = label;
}

function renderDrafts() {
  const drafts = state.workspace?.drafts || [];
  if (!drafts.some((d) => d.id === state.draftId))
    state.draftId =
      [...drafts].reverse().find((d) => d.status === "pending")?.id ||
      drafts.at(-1)?.id ||
      "";
  const pending = drafts.filter((d) => d.status === "pending").length;
  updateReviewMark(pending);
  syncRoomReviewSignal();
  $("pending-count").textContent = String(pending);
  $("table-count").textContent = pending
    ? `${pending} draft${pending === 1 ? "" : "s"} waiting for you`
    : "Your decisions come here";
  const list = $("draft-list");
  list.replaceChildren();
  if (!drafts.length)
    list.append(
      el(
        "p",
        "empty-inbox",
        "Your table is clear. Choose a desk and prepare your first draft; it will arrive here for review.",
      ),
    );
  for (const draft of [...drafts].reverse()) {
    const item = el("button", "draft-item");
    item.type = "button";
    item.setAttribute("aria-pressed", String(draft.id === state.draftId));
    const copy = el("div");
    copy.append(
      el("strong", "", draft.brief),
      el(
        "small",
        "",
        `${agentDisplayLabel(draft.agent)} · ${draftRouteLabel(draft)}`,
      ),
    );
    item.append(copy, el("span", `state-pill ${draft.status}`, draft.status));
    item.addEventListener("click", () => {
      state.draftId = draft.id;
      renderDrafts();
    });
    list.append(item);
  }
  if (!drafts.some((d) => d.id === state.draftId))
    state.draftId =
      [...drafts].reverse().find((d) => d.status === "pending")?.id ||
      drafts.at(-1)?.id ||
      "";
  const draft = drafts.find((d) => d.id === state.draftId);
  $("draft-preview").hidden = !draft;
  if (!draft) return;
  $("preview-status").textContent = draft.status;
  $("preview-status").className = `state-pill ${draft.status}`;
  $("preview-provider").textContent =
    draft.provider === "demo" ? "SIMULATED DRAFT" : draftRouteLabel(draft);
  $("preview-brief").textContent = draft.brief;
  $("preview-agent").textContent =
    `Prepared with ${agentDisplayLabel(draft.agent)}`;
  $("preview-source").hidden = !draft.source;
  $("preview-source").textContent = draft.source ? "Source file: " + fileLabel(draft.source) : "";
  $("preview-text").textContent = draft.text;
  $("decision-buttons").hidden = draft.status !== "pending";
  const download = $("download-draft");
  download.hidden = draft.status !== "approved";
  if (!download.hidden) download.href = officePath(state.selectedId, "/drafts/" + encodeURIComponent(draft.id) + "/download");
  else download.removeAttribute("href");
  $("decision-note").textContent =
    draft.status === "approved"
      ? "Approval recorded here. No outside action was performed."
      : draft.status === "declined"
        ? "Declined and kept here for reference. Prepare a new draft to revise the work."
        : "Review the complete text. Your decision is a record only.";
}
async function mutateWorkspace(path, body, after, onError) {
  if (state.busy || !state.workspace) return;
  const id = state.selectedId,
    epoch = state.epoch;
  setBusy(true);
  notice("");
  try {
    const payload = typeof body === "function" ? await body(id, epoch) : body;
    if (!isCurrent(id, epoch)) return;
    const workspace = await api(
      `/api/workspaces/${encodeURIComponent(id)}${path}`,
      payload,
    );
    if (!isCurrent(id, epoch)) return;
    state.workspace = workspace;
    if (after) after(workspace);
    renderWorkspace();
  } catch (error) {
    if (isCurrent(id, epoch)) {
      notice(error.message, true);
      if (onError) onError(error);
    }
  } finally {
    if (isCurrent(id, epoch)) setBusy(false);
  }
}

$("view-room").addEventListener("click", () => chooseOfficeView("room"));
$("view-desks").addEventListener("click", () => chooseOfficeView("desks"));
window.addEventListener("message", (event) => {
  const frame = state.roomFrame;
  if (
    !frame ||
    !state.workspace ||
    state.roomFrameId !== state.workspace.id ||
    event.source !== frame.contentWindow ||
    !localRoomURL(frame.src) ||
    event.origin !== new URL(frame.src).origin
  )
    return;
  if (event.data?.type === "office-studio:room-executive-alert") {
    if (Array.isArray(event.data) || Object.keys(event.data).length !== 2 || typeof event.data.pending !== "boolean") return;
    state.roomExecutivePending = event.data.pending;
    updateReviewMark();
    return;
  }
  if (event.data?.type === "office-studio:add-agent") {
    if (state.busy || state.workspace.crew.length >= 10) return;
    state.addingFromRoom = true;
    chooseOfficeView("desks");
    $("show-add-agent").click();
    return;
  }
  if (event.data?.type !== "office-studio:open-manual") return;
  const url = manualURL(state.workspace.manualUrl || "");
  const link = $("field-manual-link");
  link.hidden = !url;
  if (url) link.href = url;
  else link.removeAttribute("href");
  $("field-manual-note").textContent = url
    ? "Open this company's workflow reference or the local guide to using Office Studio."
    : "You can save this company's manual under Desks & drafts → Office rules & approval gates.";
  if (!$("field-manual").open) $("field-manual").showModal();
});
$("close-field-manual").addEventListener("click", () =>
  $("field-manual").close(),
);
$("manual-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const url = manualURL($("manual-url").value);
  if (url === null) {
    notice("Use an HTTPS manual URL without a username or password.", true);
    $("manual-url").focus();
    return;
  }
  mutateWorkspace("/manual", { url }, () =>
    notice(
      url
        ? "Manual link saved. It opens only when you choose it."
        : "Manual link removed.",
    ),
  );
});
$("new-office").addEventListener("click", showSetup);
$("workspace-select").addEventListener("change", (event) =>
  selectWorkspace(event.target.value),
);
$("practice").addEventListener("change", () => {
  updatePracticeLabel();
  notice("");
  $("import-pack").value = "";
  loadTemplate();
});
$("office-color").addEventListener("input", () =>
  applyAccent($("office-color").value),
);
$("office-logo").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  if (
    !["image/png", "image/jpeg", "image/webp"].includes(file.type) ||
    file.size > 200 * 1024
  ) {
    event.target.value = "";
    notice("Choose a PNG, JPEG or WebP logo no larger than 200 KB.", true);
    return;
  }
  const original = file;
  try {
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("The logo could not be read."));
      reader.readAsDataURL(file);
    });
    if ($("office-logo").files[0] !== original) return;
    if (!validLogo(data))
      throw new Error(
        "This logo could not be used. Please choose another image.",
      );
    state.logo = data;
    $("logo-preview").src = data;
    $("logo-preview").hidden = false;
    $("clear-logo").hidden = false;
    notice("");
  } catch (error) {
    notice(error.message, true);
  }
});
function clearLogo() {
  state.logo = "";
  $("office-logo").value = "";
  $("logo-preview").hidden = true;
  $("logo-preview").removeAttribute("src");
  $("clear-logo").hidden = true;
}
$("clear-logo").addEventListener("click", clearLogo);
$("import-pack").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const epoch = ++state.templateEpoch;
  state.template = null;
  state.templatePreview = null;
  state.templateMessage = "";
  $("create-office").disabled = true;
  renderTemplate();
  try {
    if (file.size > 500 * 1024)
      throw new Error("Keep intake JSON below 500 KB.");
    const pack = await prepareSetupPack(JSON.parse(await file.text()));
    if (epoch !== state.templateEpoch) return;
    state.template = pack;
    $("practice").value = "generic";
    $("practice-label").value = pack.practice || "Imported practice";
    updatePracticeLabel();
    renderTemplate();
    notice(
      "Intake crew, gates and rules imported. Keep all demonstration information synthetic.",
    );
  } catch (error) {
    if (epoch === state.templateEpoch) templateFailure(error);
  } finally {
    if (epoch === state.templateEpoch)
      $("create-office").disabled = !state.template;
  }
});
$("office-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.template) return;
  const button = $("create-office");
  button.disabled = true;
  const epoch = ++state.epoch;
  notice("Creating your office…");
  try {
    const template = state.template;
    const workspace = await api("/api/workspaces", {
      name: $("office-name").value.trim(),
      town: $("office-town").value.trim(),
      color: safeColor($("office-color").value),
      logo: state.logo,
      practice:
        $("practice").value === "generic"
          ? $("practice-label").value.trim()
          : template.practice || $("practice").value,
      crew: template.crew,
      gates: template.gates,
      rules: template.rules,
    });
    registerWorkspace(workspace);
    if (epoch !== state.epoch) return;
    state.workspace = workspace;
    state.selectedId = workspace.id;
    state.draftId = "";
    renderSelector();
    renderWorkspace();
    notice("Your office is ready. Choose Desks in the tower to meet your crew.");
    $("room-title").focus({ preventScroll: true });
    $("room-stage").scrollIntoView({ block: "start", behavior: "instant" });
  } catch (error) {
    if (epoch === state.epoch) notice(error.message, true);
  } finally {
    button.disabled = !state.template;
  }
});
$("appearance-default-color").addEventListener("change", () => {
  $("appearance-color").disabled = $("appearance-default-color").checked;
  if ($("appearance-default-color").checked)
    $("appearance-color").value = defaultAgentColor(selectedAgent());
});
function saveAppearance(reset = false) {
  const agent = selectedAgent();
  if (!agent) return;
  const title = reset ? "" : $("appearance-title").value.trim();
  const color =
    reset || $("appearance-default-color").checked
      ? ""
      : $("appearance-color").value;
  mutateWorkspace(
    "/agents/appearance",
    { agent: agent.name, title, color },
    () =>
      notice(
        "Display appearance " +
          (reset ? "reset" : "saved") +
          " for " +
          agent.name +
          ". Its name and provider route are unchanged.",
      ),
  );
}
$("save-appearance").addEventListener("click", () => saveAppearance());
$("reset-appearance").addEventListener("click", () => saveAppearance(true));
$("draft-agent").addEventListener("change", updateAgent);
$("draft-provider").addEventListener("change", updateProviderNote);
$("add-file").addEventListener("change", addWorkingFile);
$("reload-files").addEventListener("click", loadFiles);
$("delete-file").addEventListener("click", removeWorkingFile);
$("share-file").addEventListener("change", updateProviderNote);
$("draft-file").addEventListener("change", () => {
  $("file-status").textContent = "";
  renderFileLibrary();
});
$("draft-brief").addEventListener("input", () => {
  $("share-file").checked = false;
  updateProviderNote();
});
$("review-latest").addEventListener("click", () => {
  state.draftId = state.latestDraftId;
  renderDrafts();
  $("boardroom").click();
});
$("reset-attempt").addEventListener("click", () => {
  forgetFileAttempt();
  $("share-file").checked = false;
  $("reset-attempt").hidden = true;
  $("draft-feedback").textContent = "Check the file and destination, then prepare a new draft.";
  updateProviderNote();
  $("draft-brief").focus();
});
$("route-provider").addEventListener("change", () => renderRouteModels());
$("route-model").addEventListener("change", () =>
  renderRouteModels($("route-model").value),
);
$("save-route").addEventListener("click", () => {
  const agent = selectedAgent();
  if (!agent) return;
  const provider = $("route-provider").value;
  const model = provider === "demo" ? "" : $("route-model").value;
  if (
    !canSaveRoute(
      state.providers.find((p) => p.id === provider),
      model,
    )
  ) {
    notice("Choose a host-allowed model or Local demo.", true);
    return;
  }
  mutateWorkspace("/agents/route", { agent: agent.name, provider, model }, () =>
    notice(
      "Saved desk route for " +
        agent.name +
        ". No draft or outside action was performed.",
    ),
  );
});
$("draft-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const brief = $("draft-brief").value.trim();
  const override = $("draft-provider").value === "demo";
  const route = override ? { provider: "demo", model: "" } : savedRoute();
  const info = routeInfo(route);
  const provider = route.provider;
  const agent = $("draft-agent").value;
  if (!info.available) {
    notice(
      "This route is unavailable. Choose Local demo or update Desk settings.",
      true,
    );
    return;
  }
  if (!brief) {
    $("draft-brief").focus();
    return;
  }
  const body = {provider, model: info.model, agent, brief};
  const file = selectedFile();
  if (file) {
    const shareFile = provider !== "demo" && $("share-file").checked;
    if (provider !== "demo" && !shareFile) return;
    Object.assign(body, {fileId: file.id, fileVersion: file.version, shareFile});
  }
  $("draft-feedback").textContent = "Preparing your draft…";
  $("review-latest").hidden = true;
  $("reset-attempt").hidden = true;
  mutateWorkspace(
    "/drafts",
    file ? async (id, epoch) => {
      body.requestId = await fileAttempt(id, epoch, body);
      return body;
    } : body,
    (workspace) => {
      const prepared = file
        ? workspace.drafts.find((draft) => draft.requestId === body.requestId)
        : workspace.drafts.at(-1);
      state.draftId = prepared?.id || "";
      state.latestDraftId = state.draftId;
      if (file) forgetFileAttempt();
      $("share-file").checked = false;
      $("review-latest").hidden = !state.latestDraftId;
      $("draft-feedback").textContent = "Ready in your approval inbox.";
      if (override && $("draft-agent").value === agent)
        $("draft-provider").value = "route";
      notice(
        provider === "demo"
          ? "Simulated draft prepared. Review the text at your table."
          : "Draft prepared. Review the text at your table.",
      );
    },
    (error) => {
      $("draft-feedback").textContent = error.message;
      $("reset-attempt").hidden = error.code !== "draft_attempt_failed";
    },
  );
});
$("review-mark").addEventListener("click", () => {
  const office = state.workspace;
  if (!office) return;
  const saved = pendingExecutiveDraft(office);
  if (saved) {
    state.draftId = saved.id;
    renderDrafts();
  } else if (state.roomExecutivePending) {
    chooseOfficeView("room");
    state.roomFrame.focus();
    postToRoom({type: "office-studio:open-executive-alert"});
    return;
  }
  chooseOfficeView("desks");
  $("boardroom").click();
});
$("boardroom").addEventListener("click", () => {
  $("review-panel").scrollIntoView({
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "instant"
      : "smooth",
    block: "start",
  });
  $("review-panel").focus({ preventScroll: true });
});
for (const [id, decision] of [
  ["approve-draft", "approved"],
  ["decline-draft", "declined"],
])
  $(id).addEventListener("click", () => {
    if (state.draftId)
      mutateWorkspace(
        `/drafts/${encodeURIComponent(state.draftId)}/decision`,
        { decision },
        () =>
          notice(
            decision === "approved"
              ? "Approval recorded. No outside action was performed."
              : "Draft declined. No outside action was performed.",
          ),
      );
  });
$("show-add-agent").addEventListener("click", () => {
  $("add-agent-form").hidden = false;
  $("show-add-agent").hidden = true;
  $("agent-name").focus();
});
$("cancel-add-agent").addEventListener("click", () => {
  $("add-agent-form").hidden = true;
  $("show-add-agent").hidden = false;
  if (state.addingFromRoom) {
    state.addingFromRoom = false;
    chooseOfficeView("room");
    $("room-title").focus();
  }
});
$("add-agent-form").addEventListener("submit", (event) => {
  event.preventDefault();
  mutateWorkspace(
    "/agents",
    {
      name: $("agent-name").value.trim(),
      specialty: $("agent-specialty").value.trim(),
      instruction: $("agent-instruction").value.trim(),
    },
    () => {
      $("add-agent-form").reset();
      $("add-agent-form").hidden = true;
      $("show-add-agent").hidden = false;
      if (state.addingFromRoom) {
        state.addingFromRoom = false;
        chooseOfficeView("room");
        $("room-title").focus();
      }
      notice("New desk added to your office.");
    },
  );
});

async function initialize() {
  loadTemplate();
  const results = await Promise.allSettled([
    api("/api/workspaces"),
    api("/api/providers"),
  ]);
  if (results[0].status === "fulfilled") {
    // A locally created office can finish before this initial list request.
    const offices = new Map(
      (results[0].value.workspaces || []).map((office) => [office.id, office]),
    );
    for (const office of state.workspaces) offices.set(office.id, office);
    state.workspaces = [...offices.values()];
    renderSelector();
  } else
    notice(
      "The local server is unavailable. Start it, then reload this page.",
      true,
    );
  if (results[1].status === "fulfilled")
    state.providers = results[1].value.providers || [];
  else {
    state.providers = [];
    notice(
      "Provider settings could not be loaded. Reload once the local server is ready.",
      true,
    );
  }
  renderProviders();
  const savedOffice = /^#office\/([0-9a-f]{32})$/.exec(location.hash)?.[1];
  if (state.epoch === 0 && state.workspaces.some((w) => w.id === savedOffice))
    await selectWorkspace(savedOffice);
}
initialize();
