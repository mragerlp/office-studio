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
  let office, attempts = 0, queued = false;

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
    if (choice.agent === "CRIMSON" && logo && !element.querySelector("[data-office-chief-logo]")) {
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
  }

  function schedule() {
    if (!queued) { queued = true; requestAnimationFrame(decorate); }
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
      const oldColor = AGENT_COLORS[person.look.color];
      if (!oldColor) continue;
      const choice = {agent: supplied.agent, title: supplied.title, color: safeColor(supplied.color) ? supplied.color : oldColor.main};
      choices.set(id, choice);
      // Native UI draws display names; its IDs, task owners, and gate owners
      // remain the same. Presentation never changes the saved workspace crew.
      person.name = choice.title;
      person.monogram = choice.title.split(/\s+/).map(part => part[0] || "").join("").slice(0, 2).toUpperCase();
      const colorKey = "office-theme-" + id;
      const palette = {...oldColor, label: choice.title, main: choice.color, accent: choice.color};
      AGENT_COLORS[colorKey] = palette;
      person.look.color = colorKey;
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
    if (office.VIEW && typeof office.VIEW.dirty === "function") office.VIEW.dirty("main");
    document.title = presentation.name + " · Office Suite";
    document.documentElement.dataset.officeTheme = "ready";
    new MutationObserver(schedule).observe(document.body, {childList: true, subtree: true, characterData: true});
    decorate();
  }
  start();
})();
