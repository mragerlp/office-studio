/* Small browser client for Supabase Auth's authorization-code + PKCE flow. */
(() => {
  "use strict";
  const config = window.OFFICE_STUDIO_CONFIG || {};
  const base = new URL(config.url || location.origin);
  const local = base.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(base.hostname);
  const url = base.origin;
  const key = config.publishableKey || "";
  const prefix = "office-pilot:" + url + ":";
  const callback = location.origin + location.pathname;
  const identityScopes = new Map([
    ["google", "openid email profile"],
    ["azure", "email"],
    ["apple", null], // Supabase's Apple provider supplies its own scopes and form_post callback.
  ]);
  if (config.chatgptSignIn === true) identityScopes.set("custom:chatgpt", "openid profile email");
  const supportsLogin = (provider) => identityScopes.has(provider);
  let refreshPending;
  let generation = 0;
  function read(name) {
    try {
      return JSON.parse(sessionStorage.getItem(prefix + name));
    } catch {
      return null;
    }
  }
  function save(name, value) {
    sessionStorage.setItem(prefix + name, JSON.stringify(value));
  }
  function remove(name) {
    sessionStorage.removeItem(prefix + name);
  }
  async function auth(path, options = {}) {
    const r = await fetch(url + "/auth/v1/" + path, {
      ...options,
      redirect: "error",
      credentials: "omit",
      headers: { apikey: key, "Content-Type": "application/json", ...options.headers },
    });
    if (!r.ok) {
      const problem = await r.json().catch(() => ({}));
      const error = new Error(
        r.status >= 500 || r.status === 429
          ? "Sign-in service is temporarily unavailable. Try again."
          : "Sign-in could not complete. Start again or contact the office administrator.",
      );
      error.invalidRefresh = [
        "refresh_token_not_found",
        "refresh_token_already_used",
        "session_not_found",
        "invalid_grant",
      ].includes(problem.error_code || problem.code || problem.error);
      throw error;
    }
    return r.status === 204 ? null : r.json();
  }
  function storeSession(s, epoch) {
    if (epoch !== generation) throw new Error("Session changed.");
    if (!s?.access_token || !s?.refresh_token) throw new Error("The sign-in service returned no session.");
    const result = {
      access: s.access_token,
      refresh: s.refresh_token,
      expires: Date.now() + s.expires_in * 1000,
    };
    save("session", result);
    return result;
  }
  const base64url = (bytes) =>
    btoa(String.fromCharCode(...bytes)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
  async function login(provider) {
    if (!supportsLogin(provider)) throw new Error("Unknown sign-in provider.");
    const verifier = base64url(crypto.getRandomValues(new Uint8Array(64)));
    const challenge = base64url(
      new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))),
    );
    save("verifier", { verifier, time: Date.now() });
    const target = new URL(url + "/auth/v1/authorize");
    target.search = new URLSearchParams({
      provider,
      redirect_to: callback,
      code_challenge: challenge,
      code_challenge_method: "s256",
    });
    const scopes = identityScopes.get(provider);
    if (scopes) target.searchParams.set("scopes", scopes);
    location.assign(target.href);
  }
  async function init() {
    if (
      !config.url || !key || (!local && base.protocol !== "https:") || base.username || base.password ||
      base.pathname !== "/" || base.search || base.hash
    ) throw new Error("The hosted pilot needs a deployment configuration.");
    const params = new URL(location.href).searchParams;
    if (params.has("error") || new URLSearchParams(location.hash.slice(1)).has("error")) {
      history.replaceState(null, "", callback);
      remove("verifier");
      throw new Error("Sign-in was cancelled or declined. Try again.");
    }
    if (params.has("code")) {
      const code = params.get("code"), verifier = read("verifier");
      history.replaceState(null, "", callback);
      remove("verifier");
      if (!verifier || Date.now() - verifier.time > 600000) {
        throw new Error("This sign-in expired. Please start again.");
      }
      const epoch = generation;
      storeSession(
        await auth("token?grant_type=pkce", {
          method: "POST",
          body: JSON.stringify({ auth_code: code, code_verifier: verifier.verifier }),
        }),
        epoch,
      );
    }
    return !!read("session");
  }
  async function token() {
    const s = read("session");
    if (!s) throw new Error("Sign in to continue.");
    if (s.expires > Date.now() + 30000) return s.access;
    if (!refreshPending) {
      const epoch = generation;
      refreshPending = auth("token?grant_type=refresh_token", {
        method: "POST",
        body: JSON.stringify({ refresh_token: s.refresh }),
      })
        .then((next) => storeSession(next, epoch).access)
        .catch((e) => {
          if (epoch === generation && e.invalidRefresh) remove("session");
          throw e;
        })
        .finally(() => {
          refreshPending = null;
        });
    }
    return refreshPending;
  }
  async function logout() {
    const s = read("session");
    generation++;
    remove("session");
    remove("verifier");
    if (s) {
      const reply = await fetch(url + "/auth/v1/logout?scope=local", {
        method: "POST",
        headers: { apikey: key, Authorization: "Bearer " + s.access },
        credentials: "omit",
        redirect: "error",
      }).catch(() => null);
      if (!reply?.ok) {
        throw new Error("Signed out of this tab. The sign-in service could not confirm session revocation.");
      }
    }
  }
  async function request(path, options = {}) {
    const t = await token();
    const response = await fetch(url + path, {
      ...options,
      redirect: "error",
      credentials: "omit",
      headers: {
        apikey: key,
        Authorization: "Bearer " + t,
        "Content-Type": "application/json",
      },
    });
    if (!response.ok) {
      const message = path.startsWith("/functions/") ? await response.json().catch(() => null) : null;
      throw new Error(
        message?.error ||
          (response.status === 401
            ? "Session expired. Sign out and sign in again."
            : "The operation could not be completed. Check your access and selection."),
      );
    }
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }
  window.HostedAuth = { init, login, logout, request, supportsLogin };
})();
