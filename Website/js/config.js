// skilly - central frontend config, no hardcoded secrets
(function() {
  // Determine API base dynamically: allow override via window.API_BASE or meta, else use same-origin if /api/health reachable, fallback to localhost:8000 in dev
  let base = window.API_BASE || "";
  if (!base) {
    const host = location.hostname;
    const isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
    if (isLocal) {
      // dev: try same-origin first, but default to 8000 if served on 5500 (Live Server)
      const port = location.port;
      if (port === "5500" || port === "3000" || port === "5173") {
        base = `${location.protocol}//${host}:8000`;
      } else if (port === "8000") {
        base = "";
      } else {
        base = `${location.protocol}//${host}:8000`;
        // will fallback to same-origin if unreachable - handled per fetch
      }
    } else {
      base = ""; // production: same origin
    }
  }
  window.API_BASE = base;
  window.getApiUrl = function(path) {
    if (!path.startsWith("/")) path = "/" + path;
    return (window.API_BASE || "") + path;
  };
  // helper to try same-origin then localhost fallback
  window.fetchApi = async function(path, opts) {
    const url = window.getApiUrl(path);
    try {
      return await fetch(url, opts);
    } catch (e) {
      // if same-origin failed and we are on 5500, try localhost:8000
      if (!window.API_BASE && (location.port === "5500" || location.port === "3000")) {
        const fallback = `${location.protocol}//${location.hostname}:8000${path}`;
        return await fetch(fallback, opts);
      }
      throw e;
    }
  };
})();
