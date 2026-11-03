// Apply the preference before the document paints, including on the offline guide.
(() => {
  "use strict";
  const key = "office-studio:appearance";
  const system = matchMedia("(prefers-color-scheme: dark)");
  const root = document.documentElement;
  const meta = document.querySelector('meta[name="theme-color"]');
  let choice;
  try { choice = localStorage.getItem(key); } catch { /* Session only. */ }

  function apply() {
    const dark = choice === "dark" || (choice !== "light" && system.matches);
    root.dataset.appearance = dark ? "dark" : "light";
    meta.content = dark ? "#3c3c3c" : "#f5f3ed";
    for (const control of document.querySelectorAll("[data-appearance-toggle]")) {
      control.setAttribute("aria-checked", String(dark));
      control.title = dark ? "Switch to light mode" : "Switch to dark mode";
    }
    window.dispatchEvent(new Event("office-studio:appearance"));
  }

  apply();
  document.addEventListener("DOMContentLoaded", () => {
    apply();
    for (const control of document.querySelectorAll("[data-appearance-toggle]")) {
      control.addEventListener("click", () => {
        choice = root.dataset.appearance === "dark" ? "light" : "dark";
        try { localStorage.setItem(key, choice); } catch { /* Session only. */ }
        apply();
      });
    }
  });
  system.addEventListener("change", apply);
  window.addEventListener("storage", (event) => {
    if (event.key === key || event.key === null) {
      choice = event.newValue;
      apply();
    }
  });
})();
