import Alpine from "https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/module.esm.js";
import { T } from "/static/js/i18n.js";
import { icon as svgIcon } from "/static/js/icons.js";

let stream = null;
const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`;

Alpine.data("collectApp", () => ({
  token: decodeURIComponent(location.pathname.split("/c/")[1] || ""),
  lang: "en", info: null, state: "loading", items: [], camOpen: false, photoN: 0, busy: false, err: "",
  icon(name, size) { return svgIcon(name, size); },

  t(key, vars = {}) {
    let s = (T[this.lang] || T.en)[key] || T.en[key] || key;
    const all = { client: this.info?.client_name || "", purpose: this.info?.purpose || "", ...vars };
    for (const [k, v] of Object.entries(all)) s = s.replaceAll(`{${k}}`, v);
    return s;
  },
  async init() {
    const r = await fetch(`/api/collect/${encodeURIComponent(this.token)}`);
    const body = await r.json().catch(() => ({}));
    if (r.ok) {
      this.info = body; this.lang = body.language || "en";
      this.items = body.items.map((i) => ({ id: i.id, label: i.filename, status: i.status, txn_count: i.txn_count }));
      this.state = "ready";
    } else {
      const code = body?.error?.code;
      this.state = code === "expired_link" ? "expired" : code === "already_completed" ? "completed" : "invalid";
    }
  },
  get visibleItems() { return this.items.filter((i) => !i.removed); },
  get doneCount() { return this.items.filter((i) => i.status === "done").length; },
  async onFiles(ev) {
    const files = Array.from(ev.target?.files || ev.dataTransfer?.files || []);
    for (const f of files) await this.upload(f, f.name, "upload");
    if (ev.target && ev.target.value !== undefined) ev.target.value = "";
  },
  async upload(blob, filename, kind) {
    this.err = "";
    const id = uid();
    const label = kind === "camera" ? this.t("photo_n", { n: String(this.photoN) }) : filename;
    this.items.push({ id, label, status: "processing", txn_count: 0 });
    const idx = this.items.findIndex((i) => i.id === id);
    const fd = new FormData();
    fd.append("file", blob, filename);
    fd.append("kind", kind);
    try {
      const r = await fetch(`/api/collect/${encodeURIComponent(this.token)}/items`, { method: "POST", body: fd });
      const body = await r.json().catch(() => ({}));
      if (r.status === 429) {
        this.items[idx] = { ...this.items[idx], removed: true };
        this.err = this.t(body?.error?.code === "daily_limit_reached" ? "daily_limit" : "busy");
        return;
      }
      if (!r.ok) throw new Error(body?.error?.message || "error");
      this.items[idx] = { ...this.items[idx], status: body.status, txn_count: body.txn_count || 0 };
    } catch (e) {
      this.items[idx] = { ...this.items[idx], status: "failed" };
      this.err = e.message;
    }
  },
  async takePhoto() {
    if (window.matchMedia("(pointer:coarse)").matches) { this.$refs.mobileCam.click(); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } } });
      this.camOpen = true;
      this.$nextTick(() => { this.$refs.video.srcObject = stream; });
    } catch { this.err = this.t("camera_denied"); }
  },
  async capture() {
    const v = this.$refs.video;
    const c = document.createElement("canvas");
    c.width = v.videoWidth || 1280; c.height = v.videoHeight || 720;
    c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
    const blob = await new Promise((res) => c.toBlob(res, "image/jpeg", 0.92));
    this.photoN += 1;
    await this.upload(blob, `photo-${this.photoN}.jpg`, "camera");
  },
  closeCam() { if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null; this.camOpen = false; },
  async onMobilePhoto(ev) {
    const f = ev.target.files?.[0];
    if (f) { this.photoN += 1; await this.upload(f, `photo-${this.photoN}.jpg`, "camera"); }
    ev.target.value = "";
  },
  remove(id) { const i = this.items.findIndex((x) => x.id === id); if (i >= 0) this.items[i] = { ...this.items[i], removed: true }; },
  async done() {
    this.busy = true; this.err = "";
    try {
      const r = await fetch(`/api/collect/${encodeURIComponent(this.token)}/complete`, { method: "POST" });
      if (!r.ok) { const b = await r.json().catch(() => ({})); throw new Error(b?.error?.message || "error"); }
      this.closeCam();
      this.state = "thanks";
      if (window.parent !== window) window.parent.postMessage({ type: "kasflow:completed", assessmentId: this.info.assessment_id }, "*");
    } catch (e) { this.err = e.message; } finally { this.busy = false; }
  },
}));

Alpine.start();
