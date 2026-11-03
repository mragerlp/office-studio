(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const auth = window.HostedAuth, rest = (path) => auth.request("/rest/v1/" + path);
  const post = (path, data) => auth.request(path, { method: "POST", body: JSON.stringify(data) });
  const rpc = (name, data) => post("/rest/v1/rpc/office_studio_" + name, data);
  const edge = (action, fields = {}) =>
    post("/functions/v1/office-drafts", { action, office: state.office?.id, ...fields });
  const state = {
    offices: [],
    office: null,
    desks: [],
    files: [],
    runs: [],
    connection: null,
    epoch: 0,
    busy: false,
  };
  const draft = $("draft").elements, routes = $("route").elements;
  const connect = $("connect").elements;
  const labels = {
    demo: "Sample draft",
    openai: "OpenAI",
    anthropic: "Claude",
    gemini: "Gemini",
    meta: "Meta Muse",
  };
  const message = (text) => {
    $("notice").textContent = text;
  };
  function selectOptions(node, rows, label, selected = node.value) {
    node.replaceChildren(...rows.map((row) => new Option(label(row), row.id)));
    if (rows.some((row) => row.id === selected)) node.value = selected;
  }
  function clear() {
    state.epoch++;
    state.office = null;
    state.files = [];
    state.desks = [];
    state.runs = [];
    state.connection = null;
    $("workspace").hidden = true;
    $("runs").replaceChildren();
    $("title").textContent = "";
    $("draft").reset();
    $("connect").reset();
    $("upload").reset();
    $("connections").open = false;
    for (const field of [draft.file, draft.desk, routes.desk, routes.model, connect.provider]) {
      field.replaceChildren();
    }
    $("destination").textContent = "";
    $("connection-status").textContent = "";
    draft.consent.checked = false;
    window.OfficeStudioRoom?.clear();
  }
  function controls() {
    const ready = !state.busy;
    for (const b of document.querySelectorAll("button, #offices")) b.disabled = !ready;
    $("draft").querySelector("button:not([type])").disabled = !ready || !draft.file.value ||
      !draft.desk.value;
    $("remove").disabled = !ready || !draft.file.value;
    $("original").disabled = !ready || !draft.file.value;
    const p = state.connection?.providers.find((p) => p.id === connect.provider.value);
    $("connect").querySelector("button").disabled = !ready || !p?.enabled;
    $("disconnect").disabled = !ready || !p?.connected;
    $("route").querySelector("button").disabled = !ready || !state.connection;
  }
  async function work(job) {
    if (state.busy) return;
    state.busy = true;
    controls();
    message("");
    try {
      await job();
    } catch (e) {
      message(e.message || "Please try again.");
    } finally {
      state.busy = false;
      controls();
    }
  }
  function bindForm(id, job) {
    $(id).addEventListener("submit", (e) => {
      e.preventDefault();
      work(job);
    });
  }
  function download(body, filename = "approved-draft.txt") {
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function node(tag, text) {
    const n = document.createElement(tag);
    n.textContent = text;
    return n;
  }
  function showDrafts() {
    const list = $("runs");
    list.replaceChildren();
    if (!state.runs.length) {
      list.append(node("p", "Your desk’s drafts will appear here."));
      return;
    }
    for (const run of state.runs) {
      const box = node("div", "");
      box.className = "draft-card";
      const desk = state.desks.find((d) => d.id === run.desk_id),
        file = state.files.find((f) => f.id === run.file_id);
      box.append(
        node("h3", desk?.name || "Desk"),
        node(
          "p",
          (file?.name || "File") + " · " +
            (run.provider === "demo" ? "Sample draft" : labels[run.provider] + " / " + run.model) + " · " +
            run.status,
        ),
      );
      if (run.body) box.append(node("pre", run.body));
      if (run.status === "failed") {
        box.append(node("p", "This attempt failed. Submit the assignment again to start another attempt."));
      }
      if (run.status === "preparing") box.append(node("p", "Preparing. Refresh to see the result."));
      if (run.status === "review") {
        for (const label of ["Approve", "Decline"]) {
          const b = node("button", label);
          b.type = "button";
          if (label === "Decline") b.className = "quiet";
          b.onclick = () =>
            work(async () => {
              await rpc("decide", {
                p_office: state.office.id,
                p_run: run.id,
                p_decision: label === "Approve" ? "approved" : "declined",
              });
              await reload();
              message("Decision saved.");
            });
          box.append(b);
        }
      } else if (run.status === "approved") {
        const b = node("button", "Download approved draft");
        b.type = "button";
        b.onclick = () =>
          work(async () => {
            const rows = await rest(
              "office_studio_runs?select=body&office_id=eq." + state.office.id + "&id=eq." + run.id +
                "&status=eq.approved",
            );
            if (!rows.length) throw new Error("This draft is no longer available.");
            download(rows[0].body);
          });
        box.append(b);
      }
      list.append(box);
    }
  }
  function routeDestination() {
    const desk = state.desks.find((d) => d.id === draft.desk.value);
    const live = desk && desk.provider !== "demo",
      source = state.files.find((f) => f.id === draft.file.value);
    $("destination").textContent = live
      ? (source?.name || "Selected file") + " and your brief will go to " + labels[desk.provider] + " / " +
        desk.model + "."
      : "This office prepares a sample draft without sending your text to an external model.";
    $("consent-label").hidden = !live;
    draft.consent.required = live;
    draft.consent.checked = false;
  }
  function routeMenu() {
    const desk = state.desks.find((d) => d.id === routes.desk.value);
    const choices = (state.connection?.providers || []).filter((p) => p.enabled).flatMap((p) =>
      p.models.map((m) => ({ id: p.id + ":" + m, label: p.label + " / " + m }))
    );
    selectOptions(
      routes.model,
      [{ id: "", label: "Sample draft" }, ...choices],
      (r) => r.label,
      desk && desk.provider !== "demo" ? desk.provider + ":" + desk.model : "",
    );
  }
  function connectionInfo() {
    const p = state.connection?.providers.find((p) => p.id === connect.provider.value);
    $("connection-status").textContent = !state.connection
      ? "Draft service unavailable."
      : !p?.enabled
      ? "Live setup is unavailable for this provider."
      : p.connected
      ? "Key saved for this office."
      : "No key saved for this office.";
    controls();
  }
  async function reload() {
    const o = state.office;
    if (!o) return;
    const epoch = state.epoch;
    const filter = "&office_id=eq." + o.id;
    const [desks, files, runs, connection] = await Promise.all([
      rest("office_studio_desks?select=id,name,position,provider,model" + filter + "&order=position"),
      rest("office_studio_files?select=id,name,created_at" + filter + "&order=created_at.desc"),
      rest(
        "office_studio_runs?select=id,desk_id,file_id,provider,model,status,body,created_at" + filter +
          "&order=created_at.desc",
      ),
      edge("status").catch(() => null),
    ]);
    if (epoch !== state.epoch) return;
    Object.assign(state, { desks, files, runs, connection });
    selectOptions(draft.file, files, (f) => f.name + " · " + f.id.slice(0, 8));
    selectOptions(draft.desk, desks, (d) => d.name);
    selectOptions(routes.desk, desks, (d) => d.name);
    routeMenu();
    routeDestination();
    selectOptions(connect.provider, connection?.providers || [], (p) => p.label);
    connectionInfo();
    $("workspace").hidden = false;
    $("title").textContent = o.name;
    showDrafts();
    window.OfficeStudioRoom?.show({
      id: o.id,
      name: o.name,
      color: o.color,
      desks: desks.map((d) => ({ id: d.id, name: d.name })),
      pendingDeskIds: [...new Set(runs.filter((r) => r.status === "review").map((r) => r.desk_id))],
    });
    controls();
  }
  async function choose(id) {
    clear();
    state.office = state.offices.find((o) => o.id === id) || null;
    $("create").hidden = !!state.office;
    $("offices").value = id || "";
    if (state.office) await reload();
  }
  async function loadOffices(id) {
    const offices = await rest("office_studio_offices?select=id,name,color&order=name");
    state.offices = offices;
    selectOptions($("offices"), offices, (o) => o.name, id);
    $("signed").hidden = false;
    $("login").hidden = true;
    $("logout").hidden = false;
    await choose(id || offices[0]?.id || "");
  }

  for (const b of document.querySelectorAll("[data-login]")) {
    b.onclick = () => work(() => auth.login(b.dataset.login));
  }
  $("logout").onclick = () =>
    work(async () => {
      clear();
      state.offices = [];
      $("offices").replaceChildren();
      $("signed").hidden = true;
      $("login").hidden = false;
      $("logout").hidden = true;
      for (const key of Object.keys(sessionStorage)) {
        if (key.startsWith("office-run:")) sessionStorage.removeItem(key);
      }
      await auth.logout();
    });
  $("new").onclick = () => work(() => choose(""));
  $("offices").onchange = () => work(() => choose($("offices").value));
  $("refresh").onclick = () => work(() => reload());
  draft.file.onchange = routeDestination;
  draft.desk.onchange = routeDestination;
  routes.desk.onchange = routeMenu;
  draft.brief.oninput = () => {
    draft.consent.checked = false;
  };
  connect.provider.onchange = () => {
    connect.key.value = "";
    connectionInfo();
  };
  bindForm("create", async () => {
    const f = $("create").elements;
    const id = await rpc("create", { p_name: f.namedItem("name").value.trim(), p_color: f.color.value });
    $("create").reset();
    await loadOffices(id);
  });
  bindForm("upload", async () => {
    const f = $("upload").elements.file.files[0];
    if (!f || !f.name.toLowerCase().endsWith(".txt") || f.size > 65536 || !f.size) {
      throw new Error("Choose a UTF-8 .txt file between 1 byte and 64 KiB.");
    }
    let content;
    try {
      content = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(await f.arrayBuffer());
    } catch {
      throw new Error("Choose a UTF-8 text file.");
    }
    if (!content.trim() || content.includes("\u0000")) throw new Error("The file needs readable text.");
    const id = crypto.randomUUID();
    await rpc("upload", { p_office: state.office.id, p_id: id, p_name: f.name, p_content: content });
    $("upload").reset();
    await reload();
    draft.file.value = id;
    routeDestination();
    message("File saved to this office.");
  });
  $("original").onclick = () => work(async () => {
    const rows = await rest("office_studio_files?select=name,content&office_id=eq." + state.office.id +
      "&id=eq." + draft.file.value);
    if (!rows.length) throw new Error("File unavailable.");
    download(rows[0].content, rows[0].name);
  });
  $("remove").onclick = () =>
    work(async () => {
      const f = state.files.find((x) => x.id === draft.file.value);
      if (!f) return;
      if (!confirm("Delete " + f.name + " and its drafts from this office?")) return;
      await rpc("remove_file", { p_office: state.office.id, p_file: f.id });
      await reload();
      message("File and associated drafts deleted.");
    });
  bindForm("connect", async () => {
    const input = $("connect").elements.key;
    try {
      await edge("connect", { provider: connect.provider.value, key: input.value.trim() });
    } finally {
      input.value = "";
    }
    await reload();
    message("Connection saved.");
  });
  $("disconnect").onclick = () =>
    work(async () => {
      await edge("disconnect", { provider: connect.provider.value });
      await reload();
      message("Connection removed.");
    });
  bindForm("route", async () => {
    const [provider, model] = routes.model.value ? routes.model.value.split(":") : ["demo", ""];
    await edge("route", { desk: routes.desk.value, provider, model });
    await reload();
    message("Desk route saved.");
  });
  bindForm("draft", async () => {
    const desk = state.desks.find((d) => d.id === draft.desk.value);
    if (!desk || !draft.file.value) return;
    if (desk.provider !== "demo" && !draft.consent.checked) {
      throw new Error("Confirm the provider destination first.");
    }
    const request = {
      desk: desk.id,
      file: draft.file.value,
      brief: draft.brief.value.trim(),
      provider: desk.provider,
      model: desk.model,
    };
    const bytes = new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(request))),
    );
    const key = "office-run:" + state.office.id + ":" +
      Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    let id = sessionStorage.getItem(key);
    if (!id || state.runs.some((r) => r.id === id && r.status === "failed")) {
      id = crypto.randomUUID();
      sessionStorage.setItem(key, id);
    }
    try {
      const result = await edge("draft", { ...request, run: id, consent: draft.consent.checked });
      if (["review", "approved", "declined"].includes(result.status)) sessionStorage.removeItem(key);
      message(
        result.status === "review" ? "Draft ready for review." : "Draft status: " + result.status + ".",
      );
    } finally {
      await reload();
    }
  });
  work(async () => {
    if (await auth.init()) await loadOffices();
  });
})();
