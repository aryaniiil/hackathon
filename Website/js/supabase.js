// skilly - Supabase client properly initialized with backend config (no hardcoded secrets in source)
let supabaseClient = null;
let supabaseReadyPromise = null;

function getApiBaseForSupabase() {
  if (window.getApiUrl) return window.getApiUrl("/api/config");
  if (window.API_BASE !== undefined) return (window.API_BASE || "") + "/api/config";
  const host = location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1";
  if (isLocal && (location.port === "5500" || location.port === "3000" || location.port === "5173")) {
    return `${location.protocol}//${host}:8000/api/config`;
  }
  return "/api/config";
}

async function initSupabase() {
  if (supabaseClient) return supabaseClient;
  if (!window.supabase) {
    console.warn("[supabase] CDN not loaded - auth will fallback to Python backend");
    return null;
  }
  try {
    const cfgUrl = getApiBaseForSupabase();
    const r = await fetch(cfgUrl);
    if (!r.ok) throw new Error("config fetch failed " + r.status);
    const cfg = await r.json();
    const url = cfg.supabase_url;
    const anon = cfg.supabase_anon_key;
    if (!url || !anon) {
      console.warn("[supabase] no url/anon in config, trying fallback");
      return null;
    }
    supabaseClient = window.supabase.createClient(url, anon);
    window.supabaseClient = supabaseClient;
    console.log("[supabase] initialized", url);
    return supabaseClient;
  } catch (e) {
    console.warn("[supabase] init failed, will use Python backend auth:", e.message);
    return null;
  }
}

// Start init immediately but don't block
supabaseReadyPromise = initSupabase();

async function getSupabase() {
  if (supabaseClient) return supabaseClient;
  if (supabaseReadyPromise) {
    await supabaseReadyPromise;
  } else {
    await initSupabase();
  }
  return supabaseClient;
}

// Helpers used by auth pages - now properly handle Supabase with OTP
async function requireAuth() {
  const client = await getSupabase();
  if (client) {
    const { data: { session } } = await client.auth.getSession();
    if (session) return session;
  }
  // fallback to Python backend token
  const token = localStorage.getItem("skilly_token");
  if (token) {
    try {
      const r = await fetch((window.getApiUrl ? window.getApiUrl("/api/auth/me") : "/api/auth/me"), {
        headers: { Authorization: "Bearer " + token }
      });
      if (r.ok) {
        const u = await r.json();
        return { user: u, token };
      }
    } catch {}
  }
  // also check local demo
  const localUser = JSON.parse(localStorage.getItem("skilly_user") || "null");
  if (localUser && localUser.demo) return { user: localUser };
  window.location.href = "signin.html";
  return null;
}

async function signOutAndRedirect() {
  const client = await getSupabase();
  if (client) {
    try { await client.auth.signOut(); } catch {}
  }
  localStorage.removeItem("skilly_token");
  localStorage.removeItem("skilly_user");
  // keep history? user said don't store locally but we keep server history
  window.location.href = "signin.html";
}

// expose
window.getSupabase = getSupabase;
window.supabaseReadyPromise = supabaseReadyPromise;
// will be set after init, but also expose getter
Object.defineProperty(window, 'supabaseClient', {
  get() { return supabaseClient; },
  set(v) { supabaseClient = v; }
});
window.requireAuth = requireAuth;
window.signOutAndRedirect = signOutAndRedirect;
