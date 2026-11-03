// Send only presentation fields to the opaque-origin room. Drafts and documents stay in Studio.
(() => {
  let office = null, layout = null, ready = false;
  const frame = () => document.getElementById("office-room");
  function send() {
    if (!ready || !office) return;
    // The iframe has an opaque origin. Only this frame receives display data.
    const target = frame().contentWindow;
    target.postMessage({ type: "studio:room-state", office }, "*");
    target.postMessage({
      type: "office-studio:review-signal",
      pending: office.waiting.some(Boolean),
      executivePending: office.waiting[0],
    }, "*");
    target.postMessage({
      type: "office-studio:appearance",
      mode: document.documentElement.dataset.appearance,
    }, "*");
  }
  function clear() {
    const old = frame();
    office = null;
    ready = false;
    layout = null;
    document.getElementById("room-loading").hidden = true;
    const mark = document.getElementById("office-mark");
    mark.removeAttribute("href");
    mark.setAttribute("aria-disabled", "true");
    mark.setAttribute("aria-label", "Office Studio");
    delete mark.dataset.waiting;
    mark.style.removeProperty("--accent");
    if (!old || !old.hasAttribute("src")) return;
    const fresh = old.cloneNode(false);
    fresh.removeAttribute("src");
    fresh.hidden = true;
    old.replaceWith(fresh);
  }
  function show(value) {
    if (!value?.id || !Array.isArray(value.desks) || !value.desks.length) {
      return clear();
    }
    const desks = value.desks.slice(0, 10).map((desk, index) => ({
      id: String(desk.id),
      name: String(desk.title || desk.name || "Desk " + (index + 1)).slice(
        0,
        60,
      ),
      specialty: String(
        desk.specialty || desk.title || desk.name || "Office work",
      ).slice(0, 120),
    }));
    const info = {
      id: String(value.id),
      name: String(value.name).slice(0, 100),
      color: /^#[0-9a-f]{6}$/i.test(value.color) ? value.color : "#000000",
      desks,
    };
    // Appended desks can be seated in the live scene. Changed identities, order,
    // or appearance require a fresh isolated context.
    const compatible = layout && layout.id === info.id && layout.name === info.name &&
      layout.color === info.color && layout.desks.every((old, i) => {
        const desk = desks[i];
        return desk && desk.id === old.id && desk.name === old.name && desk.specialty === old.specialty;
      });
    if (!compatible) {
      clear();
      document.getElementById("room-loading").hidden = false;
      const room = frame();
      room.hidden = false;
      const mode = document.documentElement.dataset.appearance === "dark"
        ? "dark"
        : "light";
      room.src = "./suite-room.html?pack=hosted&view=overview&appearance=" +
        mode;
    }
    layout = info;
    const pending = new Set((value.pendingDeskIds || []).map(String));
    office = {
      name: info.name,
      color: info.color,
      desks: desks.map(({ name, specialty }) => ({ name, specialty })),
      waiting: desks.map((desk) => pending.has(desk.id)),
    };
    const mark = document.getElementById("office-mark");
    mark.href = "#review";
    mark.removeAttribute("aria-disabled");
    mark.style.setProperty("--accent", info.color);
    mark.dataset.waiting = String(office.waiting[0]);
    mark.setAttribute(
      "aria-label",
      office.waiting[0]
        ? "Head Executive needs your review"
        : "Open the boardroom",
    );
    send();
  }
  window.addEventListener("message", (e) => {
    if (e.origin !== "null" || e.source !== frame()?.contentWindow || !office) return;
    if (e.data?.type === "studio:room-ready") {
      ready = true;
      send();
    } else if (e.data?.type === "studio:room-mounted") {
      document.getElementById("room-loading").hidden = true;
      send();
    } else if (e.data?.type === "studio:open-board") {
      document.getElementById("review").focus();
    } else if (e.data?.type === "office-studio:add-agent") {
      document.getElementById("hosted-add-desk").open = true;
      document.getElementById("desk-name").focus();
    } else if (e.data?.type === "office-studio:open-manual") {
      document.getElementById("hosted-help").focus();
    }
  });
  window.OfficeStudioRoom = { show, clear };
  window.addEventListener("office-studio:appearance", send);
})();
