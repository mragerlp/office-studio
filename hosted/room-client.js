// Runs inside a sandbox without same-origin privileges or network access.
(() => {
  const origin = new URL(location.href).origin;
  document.documentElement.dataset.appearance =
    new URLSearchParams(location.search).get("appearance") === "dark"
      ? "dark"
      : "light";
  let begin, current, mounted = false;
  const pack = new Promise((resolve) => {
    begin = resolve;
  });
  const palette = [
    "crimson",
    "azure",
    "green",
    "violet",
    "orange",
    "teal",
    "slate",
    "lime",
    "plum",
    "olive",
  ];
  function refresh() {
    if (!mounted) return;
    const api = window.AgentOffice;
    for (const [i, id] of api.state.order.entries()) {
      const waiting = !!current.waiting[i];
      const status = waiting ? "WAITING" : "IDLE";
      const detail = waiting
        ? "Draft awaiting review"
        : "Ready for a file brief";
      const desk = api.state.agents[id];
      if (desk.status !== status || desk.detail !== detail) {
        api.setAgentStatus(id, status, { detail });
      }
    }
  }
  window.addEventListener("message", ({ source, origin: sender, data }) => {
    if (
      source !== parent || sender !== origin ||
      data?.type !== "studio:room-state"
    ) return;
    const view = data.office;
    if (
      !view || !Array.isArray(view.desks) || !view.desks.length ||
      view.desks.length > 10 ||
      !Array.isArray(view.waiting) || typeof view.name !== "string"
    ) return;
    current = view;
    if (begin) {
      const crew = view.desks.map((d, i) => ({
        name: i ? "DESK" + i : "CRIMSON",
        specialty: String(d.specialty || "Office work"),
        instruction: "Review assigned work in the office inbox.",
        engine: "Office Studio",
        systems: [],
        style: "headset",
        color: palette[i],
      }));
      const presentation = document.createElement("script");
      presentation.type = "application/json";
      presentation.id = "office-studio-presentation";
      presentation.textContent = JSON.stringify({
        name: view.name,
        color: view.color,
        studioOrigin: origin,
        agents: crew.map((d, i) => ({
          agent: d.name,
          title: view.desks[i].name,
          executive: i === 0,
          color: i === 0 ? view.color : "",
        })),
      });
      document.head.append(presentation);
      begin({
        office: view.name,
        feed: "simulated",
        systems: [],
        rules: "Review saved drafts in the office inbox.",
        crew,
        gates: [],
      });
      begin = null;
    }
    refresh();
  });
  window.OfficeStudioHostedRoom = {
    pack,
    mounted() {
      goLive();
      FEED_NOTES.hosted =
        "Office inbox status. Open a draft in the workspace to review it.";
      OFFICE_STATE.meta.feed = "hosted";
      UI.renderFeed();
      mounted = true;
      refresh();
      parent.postMessage({ type: "studio:room-ready" }, origin);
    },
  };
  parent.postMessage({ type: "studio:room-ready" }, origin);
})();
