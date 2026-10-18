const cfg = window.KASFLOW_CONFIG || { authMode: "stub", firebase: {} };
const STUB_KEY = "kasflow_stub_token";
const SDK = "https://www.gstatic.com/firebasejs/10.12.2";
let fb = null;

export const authMode = cfg.authMode;

async function loadFirebase() {
  if (fb) return fb;
  const appMod = await import(`${SDK}/firebase-app.js`);
  const authMod = await import(`${SDK}/firebase-auth.js`);
  const app = appMod.initializeApp(cfg.firebase);
  fb = { auth: authMod.getAuth(app), m: authMod };
  return fb;
}

function stubGet() { try { return localStorage.getItem(STUB_KEY); } catch { return null; } }
function stubSet(v) { try { v ? localStorage.setItem(STUB_KEY, v) : localStorage.removeItem(STUB_KEY); } catch { /* ignore */ } }

export async function signInGoogle() {
  if (authMode === "stub") { stubSet("stub:dev-analyst@kasflow.local"); return; }
  const { auth, m } = await loadFirebase();
  await m.signInWithPopup(auth, new m.GoogleAuthProvider());
}

export async function signInCustom(token) {
  if (authMode === "stub") { stubSet(token); return; }
  const { auth, m } = await loadFirebase();
  await m.signInWithCustomToken(auth, token);
}

export async function signOut() {
  stubSet(null);
  if (authMode !== "stub") { const { auth, m } = await loadFirebase(); await m.signOut(auth); }
}

export async function currentUser() {
  if (authMode === "stub") { const t = stubGet(); return t ? { email: t.slice(5) } : null; }
  const { auth } = await loadFirebase();
  await auth.authStateReady();
  return auth.currentUser ? { email: auth.currentUser.email || "demo-analyst@kasflow.demo" } : null;
}

export async function getIdToken() {
  if (authMode === "stub") return stubGet();
  const { auth } = await loadFirebase();
  await auth.authStateReady();
  return auth.currentUser ? auth.currentUser.getIdToken() : null;
}

export async function api(path, opts = {}) {
  const token = await getIdToken();
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const init = { method: opts.method || "GET", headers };
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.json); }
  const res = await fetch(path, init);
  if (res.status === 401) { window.location.href = "/"; throw new Error("Please sign in again"); }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.error?.message || `HTTP ${res.status}`);
  return body;
}
