const BACKEND_URL = "http://skillyhackathon.duckdns.org/"; 
(function() {
  let base = BACKEND_URL || window.API_BASE || "";
  if (!base) {
    const meta = document.querySelector('meta[name="api-base"]');
    if (meta) base = meta.getAttribute("content") || "";
  }
  if (!base) {
    const host = location.hostname;
    const isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
    if (isLocal) {
      const port = location.port;
      if (port === "5500" || port === "3000" || port === "5173" || port === "8001" || port === "5000") {
        base = "";
      } else if (port === "8000" || port === "8001") {
        base = "";
      } else {
        base = "";
      }
    } else {
      base = "";
    }
  }
  window.API_BASE = base;
  window.getApiUrl = function(path) {
    if (!path.startsWith("/")) path = "/" + path;
    return (window.API_BASE || "") + path;
  };
  window.fetchApi = async function(path, opts) {
    const url = window.getApiUrl(path);
    try {
      return await fetch(url, opts);
    } catch (e) {
      if (!window.API_BASE && (location.port === "5500" || location.port === "3000" || location.port === "5173")) {
        const tryPorts = ["8000", "8001", "5000"];
        for (const p of tryPorts) {
          try {
            const fallback = `${location.protocol}//${location.hostname}:${p}${path}`;
            const r = await fetch(fallback, opts);
            window.API_BASE = `${location.protocol}//${location.hostname}:${p}`;
            return r;
          } catch {}
        }
      }
      throw e;
    }
  };
})();
