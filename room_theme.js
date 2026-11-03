/* Office Studio presentation adapter. Original room source remains untouched. */
(() => {
  "use strict";
  const input = document.getElementById("office-studio-presentation");
  if (!input) return;
  let presentation;
  try { presentation = JSON.parse(input.textContent); } catch { return; }
  if (!presentation || typeof presentation.name !== "string" || !Array.isArray(presentation.agents)) return;
  const safeColor = value => typeof value === "string" && /^#[\da-f]{6}$/i.test(value);
  const safeLogo = value => typeof value === "string" && value.length <= 700000 && /^data:image\/(png|jpeg|webp);base64,[\da-z+/=]+$/i.test(value);
  const logo = safeLogo(presentation.logo) ? presentation.logo : "";
  const choices = new Map();
  const suppliedAgents = new Map(presentation.agents.filter(item => item && typeof item.agent === "string" &&
    typeof item.title === "string").map(item => [item.agent, item]));
  const executiveInfo = [...suppliedAgents.values()].some(item => typeof item.executive === "boolean");
  const executiveAliases = new Set([...suppliedAgents.values()]
    .filter(item => executiveInfo ? item.executive === true : item.agent === "CRIMSON")
    .map(item => item.agent));
  const executiveIds = new Set(executiveInfo ? [] : ["crimson"]);
  const knownIds = new Map();
  let office, attempts = 0, queued = false, ownerReviewPending = false, ownerExecutivePending = false,
    reviewSculpture = null, refreshSculptureAlert = null;

  function nativeExecutiveGate() {
    const state = office && office.OFFICE_STATE;
    // Seeded simulated gates are still visible approvals for the executive.
    // Display titles/statuses are presentation and are not ownership sensors.
    return Array.isArray(state?.approvals) && state.approvals.find(gate => executiveIds.has(gate.agentId));
  }

  function markReviewSignal() {
    if (!reviewSculpture) return;
    reviewSculpture.group.userData.officeStudioReviewPending = ownerReviewPending;
    reviewSculpture.group.userData.officeStudioExecutivePending = ownerExecutivePending;
    document.documentElement.dataset.officeReviewPending = String(ownerReviewPending);
    document.documentElement.dataset.officeExecutivePending = String(ownerExecutivePending);
    if (refreshSculptureAlert) refreshSculptureAlert();
  }

  // Accept only the Studio parent's appearance, review flags and open-alert action.
  // The old two-key review signal still indicates generic attention.
  if (window.parent !== window && typeof window.addEventListener === "function") {
    window.addEventListener("message", event => {
      const data = event.data;
      if (event.source !== window.parent || event.origin !== presentation.studioOrigin ||
          !data || typeof data !== "object" || Array.isArray(data)) return;
      const keys = Object.keys(data);
      if (keys.length === 2 && data.type === "office-studio:appearance" && keys.includes("mode") &&
          (data.mode === "light" || data.mode === "dark")) {
        document.documentElement.dataset.appearance = data.mode;
        if (typeof updateStudioExposure === "function") updateStudioExposure();
        return;
      }
      if (keys.length === 1 && data.type === "office-studio:open-executive-alert") {
        const gate = nativeExecutiveGate();
        if (gate && typeof office.UI.select === "function") {
          if (document.getElementById("board")?.hidden === false) office.UI.toggleBoard(false);
          office.UI.select(gate.agentId);
          const panel = document.getElementById("panel");
          if (panel) { panel.tabIndex = -1; panel.focus({preventScroll: true}); }
        }
        return;
      }
      const legacy = keys.length === 2 && keys.includes("type") && keys.includes("pending");
      const current = keys.length === 3 && keys.includes("type") && keys.includes("pending") &&
        keys.includes("executivePending") && typeof data.executivePending === "boolean";
      if ((!legacy && !current) || data.type !== "office-studio:review-signal" || typeof data.pending !== "boolean") return;
      ownerReviewPending = data.pending;
      ownerExecutivePending = current ? data.executivePending : false;
      markReviewSignal();
    });
  }

  function preparePaint(person) {
    if (!person || !person.look || typeof AGENT_COLORS !== "object") return null;
    const supplied = suppliedAgents.get(person.name);
    if (!supplied || (knownIds.has(supplied.agent) && knownIds.get(supplied.agent) !== person.id)) return null;
    if (choices.has(person.id)) return choices.get(person.id);
    const original = AGENT_COLORS[person.look.color];
    if (!original) return null;
    const chosen = safeColor(supplied.color);
    const choice = {agent: supplied.agent, title: supplied.title, color: chosen ? supplied.color : original.main};
    const colorKey = "office-theme-" + person.id;
    const palette = {...original, label: choice.title, main: choice.color, accent: choice.color};
    AGENT_COLORS[colorKey] = palette;
    person.look.color = colorKey;
    if (chosen) person.look.bot = {...person.look.bot, paint: choice.color, deep: 0};
    // Do not change the display name here: the room still builds its gate
    // owner-name lookup immediately after publishing each add event.
    knownIds.set(supplied.agent, person.id);
    if (executiveAliases.has(supplied.agent)) executiveIds.add(person.id);
    choices.set(person.id, choice);
    return choice;
  }

  // The public event API exists before asynchronous boot fetches/seats the
  // pack. Install once now, so Figure receives the owner's paint at birth.
  if (window.AgentOffice && typeof window.AgentOffice.on === "function") {
    window.AgentOffice.on("add", preparePaint);
    window.AgentOffice.on("approval", markReviewSignal);
  }

  function logoImage(marker, label) {
    const image = document.createElement("img");
    image.src = logo;
    image.alt = label;
    image.setAttribute(marker, "");
    image.style.cssText = "width:100%;height:100%;object-fit:contain;box-sizing:border-box;padding:3px;border-radius:inherit";
    return image;
  }

  function badge(element, id) {
    const choice = choices.get(id);
    if (!element || !choice) return;
    element.dataset.officeAgentBadge = id;
    element.setAttribute("aria-label", choice.title);
    if (choice.color) element.style.setProperty("--c", choice.color);
    if (executiveAliases.has(choice.agent) && logo && !element.querySelector("[data-office-chief-logo]")) {
      element.replaceChildren(logoImage("data-office-chief-logo", presentation.name + " · " + choice.title));
    }
  }

  function decorate() {
    queued = false;
    for (const wordmark of document.querySelectorAll("#topbar .wordmark, #mirror .wordmark")) {
      if (wordmark.textContent !== presentation.name) wordmark.textContent = presentation.name;
      wordmark.setAttribute("aria-label", presentation.name);
      wordmark.style.cssText = "font-family:inherit;font-size:19px;letter-spacing:0;text-transform:none;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
    }
    const title = document.querySelector("#topbar .brand .title");
    if (title && title.textContent !== "OFFICE SUITE") title.textContent = "OFFICE SUITE";
    const brand = document.querySelector("#topbar .brand");
    if (brand && logo && !brand.querySelector("[data-office-brand-logo]")) {
      const image = logoImage("data-office-brand-logo", presentation.name);
      image.style.cssText = "width:32px;height:32px;object-fit:contain;margin-right:8px";
      brand.prepend(image);
    }
    for (const [id] of choices) {
      const row = document.getElementById("r-" + id);
      badge(row && row.querySelector(".tile"), id);
      const bubble = office.UI.bubbles && office.UI.bubbles[id];
      badge(bubble && bubble.el.querySelector(".dot"), id);
    }
    badge(document.querySelector("#panel .tile"), office.UI.selected);
    badge(document.querySelector("#hovercard .tile"), office.UI.hoverId);
    const state = office.OFFICE_STATE;
    const panel = document.getElementById("panel");
    const panelOpen = office.UI.selected && panel && !panel.hidden;
    const gate = panelOpen ? state.approvals.find(item => item.agentId !== office.UI.selected) : state.approvals[0];
    if (gate) badge(document.querySelector("#gate .tile"), gate.agentId);
    for (const [selector, column] of [["#colQueued", "queued"], ["#colProgress", "progress"], ["#colDone", "done"]]) {
      const container = document.querySelector(selector);
      if (!container) continue;
      let tasks = state.tasks.filter(task => task.column === column);
      if (column === "done") tasks = tasks.sort((x, y) => y.record === x.record ? y.at - x.at : x.record ? 1 : -1).slice(0, 60);
      container.querySelectorAll(".card").forEach((card, index) => {
        if (tasks[index]) badge(card.querySelector(".tile"), tasks[index].agentId);
      });
    }
  }

  function schedule() {
    if (!queued) { queued = true; requestAnimationFrame(decorate); }
  }

  function tintExistingAmpersand() {
    const sculpture = office.ROOM_OBJ && office.ROOM_OBJ.sculpture;
    if (!sculpture || !sculpture.group || !sculpture.base || !safeColor(presentation.color) ||
        !office.THREE || typeof office.THREE.Color !== "function") return;
    const base = sculpture.base;
    if (!(base.r + base.g + base.b > 0) || typeof base.copy !== "function") return;
    let painted = "", executiveAlert = false, reportedNative;
    const gains = new Map();
    function paint(hex) {
      if (painted === hex) return;
      const sum = base.r + base.g + base.b;
      const tint = new office.THREE.Color(hex).convertSRGBToLinear();
      // Retint dedicated materials only. Read current gains so the native
      // reveal pulse retains its brightness when an alert changes tiers.
      for (const name of ["lacquer", "haloMat", "topMat", "poolMat", "revealMat"]) {
        const material = sculpture[name];
        if (!material) continue;
        for (const property of name === "lacquer" ? ["color", "emissive"] : ["color"]) {
          const color = material[property];
          if (!color || typeof color.copy !== "function" || typeof color.multiplyScalar !== "function") continue;
          const gain = sum > 0 ? (color.r + color.g + color.b) / sum : gains.get(color);
          if (Number.isFinite(gain) && gain >= 0) {
            gains.set(color, gain);
            color.copy(tint).multiplyScalar(gain);
          }
        }
      }
      base.copy(tint);
      painted = hex;
      sculpture.group.userData.officeStudioAmpColor = hex;
      document.documentElement.dataset.officeAmpColor = hex;
    }
    refreshSculptureAlert = () => {
      const native = !!nativeExecutiveGate();
      if (native !== reportedNative && window.parent !== window) {
        // Report only the native flag. Echoing the combined flag would latch
        // a saved draft's alert after the owner cleared it in the Studio.
        window.parent.postMessage({type: "office-studio:room-executive-alert", pending: native}, presentation.studioOrigin);
        reportedNative = native;
      }
      const executive = native || ownerExecutivePending;
      executiveAlert = executive;
      sculpture.group.userData.officeStudioNativeExecutivePending = native;
      sculpture.group.userData.officeStudioExecutiveAlert = executive;
      document.documentElement.dataset.officeNativeExecutivePending = String(native);
      document.documentElement.dataset.officeExecutiveAlert = String(executive);
      paint(executive ? "#a70008" : presentation.color);
      return executive;
    };
    sculpture.group.userData.officeStudioAmpBrandColor = presentation.color;
    document.documentElement.dataset.officeAmpBrandColor = presentation.color;
    // The native loop remains the sole clock, including reduced-motion rules.
    // Its writes retain realIssues. Reads combine that result with actual
    // executive approvals and the parent's saved-review flags, without gates.
    const fast = Object.getOwnPropertyDescriptor(sculpture, "fast");
    if (!fast || fast.configurable) {
      let nativeFast = Boolean(sculpture.fast);
      sculpture.group.userData.officeStudioNativeFast = nativeFast;
      Object.defineProperty(sculpture, "fast", {configurable: true, enumerable: true,
        get: () => nativeFast || ownerReviewPending || executiveAlert,
        set: value => {
          nativeFast = Boolean(value);
          sculpture.group.userData.officeStudioNativeFast = nativeFast;
          refreshSculptureAlert();
        }});
      reviewSculpture = sculpture;
      markReviewSignal();
    }
    sculpture.group.userData.officeStudioAmpSource = "native-real-issues-or-owner-review";
    document.documentElement.dataset.officeAmpSource = "native-real-issues-or-owner-review";
    refreshSculptureAlert();
  }

  function start() {
    office = window.__office;
    if (!office || !office.UI || !office.OFFICE_STATE || !document.querySelector("#topbar .brand") ||
        typeof AGENT_COLORS !== "object") {
      if (++attempts < 300) setTimeout(start, 100);
      else document.documentElement.dataset.officeTheme = "unsupported";
      return;
    }
    const state = office.OFFICE_STATE;
    for (const supplied of presentation.agents) {
      if (!supplied || typeof supplied.agent !== "string" || typeof supplied.title !== "string") continue;
      const id = state.order.find(key => state.agents[key].name === supplied.agent);
      if (!id) continue;
      const person = state.agents[id];
      const choice = choices.get(id) || preparePaint(person);
      if (!choice) continue;
      // Native UI draws display names; its IDs, task owners, and gate owners
      // remain the same. Presentation never changes the saved workspace crew.
      person.name = choice.title;
      person.monogram = choice.title.split(/\s+/).map(part => part[0] || "").join("").slice(0, 2).toUpperCase();
      const palette = AGENT_COLORS[person.look.color];
      const rendered = office.WORLD && office.WORLD.byId[id];
      if (rendered && rendered.fig) rendered.fig.colors = palette;
      if (rendered && rendered.st) {
        const station = rendered.st;
        station.C = palette;
        station.idHex = choice.color;
        station.spec.name = choice.title;
        if (typeof plateTexture === "function" && station.plateMat) {
          const previous = [station.plateTex, station.plateWaitTex];
          station.plateTex = plateTexture(choice.title, person.specialty, "#ffffff", "#ffffff");
          station.plateWaitTex = plateTexture(choice.title, person.specialty, choice.color, "#ffffff");
          station.plateMat.map = person.status === "WAITING" ? station.plateWaitTex : station.plateTex;
          station.plateMat.needsUpdate = true;
          previous.forEach(texture => texture && texture.dispose());
        }
      }
      if (typeof office.UI.renderRosterRow === "function") office.UI.renderRosterRow(id);
      if (typeof office.UI.renderBubble === "function") office.UI.renderBubble(id);
    }
    for (const name of ["renderRosterRow", "renderBubble", "renderPanel", "renderHover", "renderGate", "renderBoard", "renderMirror"]) {
      const original = office.UI[name];
      if (typeof original !== "function") continue;
      office.UI[name] = function (...args) { const value = original.apply(this, args); schedule(); return value; };
    }
    if (typeof office.UI.renderGate === "function") office.UI.renderGate();
    if (office.VIEW && typeof office.VIEW.dirty === "function") office.VIEW.dirty("main");
    tintExistingAmpersand();
    if (window.parent !== window) {
      const notifyStudio = type => window.parent.postMessage({type}, presentation.studioOrigin);
      if (typeof office.UI.openManual === "function") {
        office.UI.openManual = () => notifyStudio("office-studio:open-manual");
      }
      if (typeof office.UI.openAdd === "function") {
        office.UI.openAdd = () => notifyStudio("office-studio:add-agent");
      }
    }
    document.title = presentation.name + " · Office Suite";
    document.documentElement.dataset.officeTheme = "ready";
    new MutationObserver(schedule).observe(document.body, {childList: true, subtree: true, characterData: true});
    decorate();
  }
  start();
})();
