import Alpine from "https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/module.esm.js";
import { api, currentUser, signOut } from "/static/js/firebase.js";

const FLAGS = { ID: "🇮🇩", PH: "🇵🇭", VN: "🇻🇳" };
const LOCALE = { ID: "id-ID", PH: "en-PH", VN: "vi-VN" };
const STATUS = { created: "Created", needs_more_data: "Needs more data", scored: "Scored", reviewed: "Reviewed", error: "Error" };
const ICON = { open_finance: "🏦", api_push: "🔌", upload: "📄", camera: "📷" };
let chart = null;

Alpine.data("consoleApp", () => ({
  user: null, route: "list", list: [], filter: "all", a: null, txns: [], link: null, busy: "", error: "",
  showLocal: true, expanded: {}, review: { action: "accept", final_recommendation: "review", note: "" },
  filters: [{ key: "all", label: "All" }, { key: "needs_more_data", label: "Needs more data" },
            { key: "scored", label: "Scored" }, { key: "reviewed", label: "Reviewed" }, { key: "error", label: "Error" }],

  async init() {
    this.user = await currentUser();
    if (!this.user) { location.href = "/"; return; }
    window.addEventListener("hashchange", () => this.navigate());
    await this.navigate();
    setInterval(() => this.refresh(), 5000);
  },
  async navigate() {
    const m = location.hash.match(/^#a\/(.+)$/);
    this.error = ""; this.link = null; this.expanded = {};
    if (m) { this.route = "detail"; this.a = null; await this.loadDetail(m[1]); }
    else { this.route = "list"; this.a = null; await this.loadList(); }
  },
  async refresh() {
    if (this.busy) return;
    if (this.route === "list") await this.loadList();
    else if (this.a && this.a.status === "needs_more_data") await this.loadDetail(this.a.id, true);
  },
  async loadList() {
    try { this.list = (await api("/api/console/assessments")).items; } catch (e) { this.error = e.message; }
  },
  get filtered() { return this.filter === "all" ? this.list : this.list.filter((x) => x.status === this.filter); },
  async loadDetail(id, quiet = false) {
    try {
      const a = await api(`/api/console/assessments/${id}`);
      const t = await api(`/api/console/assessments/${id}/transactions`);
      const changed = !this.a || this.a.updated_at !== a.updated_at;
      this.a = a; this.txns = t.items;
      if (changed) this.$nextTick(() => this.drawChart());
    } catch (e) { if (!quiet) this.error = e.message; }
  },
  async act(name, fn) {
    this.busy = name; this.error = "";
    try { await fn(); } catch (e) { this.error = e.message; } finally { this.busy = ""; }
  },
  genLink() { return this.act("link", async () => { this.link = await api(`/api/console/assessments/${this.a.id}/collection-link`, { method: "POST" }); await this.loadDetail(this.a.id); }); },
  scoreNow() { return this.act("score", async () => { await api(`/api/console/assessments/${this.a.id}/score`, { method: "POST" }); await this.loadDetail(this.a.id); }); },
  regen() { return this.act("summary", async () => { await api(`/api/console/assessments/${this.a.id}/summary`, { method: "POST" }); await this.loadDetail(this.a.id); }); },
  submitReview() {
    return this.act("review", async () => {
      const body = { action: this.review.action, note: this.review.note };
      if (this.review.action === "override") body.final_recommendation = this.review.final_recommendation;
      await api(`/api/console/assessments/${this.a.id}/review`, { method: "POST", json: body });
      await this.loadDetail(this.a.id);
    });
  },
  async logout() { await signOut(); location.href = "/"; },

  flag(c) { return FLAGS[c] || c; },
  kindIcon(k) { return ICON[k] || "•"; },
  statusLabel(s) { return STATUS[s] || s; },
  statusClass(s) {
    return { needs_more_data: "bg-amber-100 text-amber-800", scored: "bg-sky-100 text-sky-800",
             reviewed: "bg-emerald-100 text-emerald-800", error: "bg-red-100 text-red-700" }[s] || "bg-slate-100 text-slate-700";
  },
  recClass(r) {
    return { favorable: "bg-emerald-100 text-emerald-800", review: "bg-amber-100 text-amber-800",
             unfavorable: "bg-red-100 text-red-700" }[r] || "bg-slate-100";
  },
  gradeColor() { return { A: "#059669", B: "#10b981", C: "#f59e0b", D: "#dc2626" }[this.a?.result?.grade] || "#94a3b8"; },
  dash() { const c = 2 * Math.PI * 50; return `${((this.a?.result?.score || 0) / 100) * c} ${c}`; },
  money(v) {
    if (v === null || v === undefined || v === "") return "—";
    return new Intl.NumberFormat(LOCALE[this.a?.customer?.country] || "en", { style: "currency", currency: this.a?.currency || "USD", maximumFractionDigits: 0 }).format(Number(v));
  },
  pct(v) { return v === null || v === undefined ? "—" : `${(Number(v) * 100).toFixed(1)}%`; },
  dateStr(s) { return s ? new Date(s).toLocaleString() : ""; },
  ago(s) {
    const sec = Math.max(0, (Date.now() - new Date(s).getTime()) / 1000);
    if (sec < 60) return "just now"; if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`; return `${Math.floor(sec / 86400)}d ago`;
  },
  sourceTxns(sid) { return this.txns.filter((t) => t.source_id === sid); },
  rowClass(t) {
    if (t.tampered) return "bg-red-50 text-red-800";
    if (t.duplicate_of || t.kind === "internal_transfer") return "text-slate-400";
    return "";
  },
  rowNote(t, s) {
    if (t.tampered) {
      const f = s.tamper_flags.find((x) => x.row_index === t.row_index);
      return `⚠ Balance mismatch — expected ${this.money(f?.expected_balance)}`;
    }
    if (t.duplicate_of) return "Duplicate of a more trusted source";
    if (t.kind === "internal_transfer") return "Internal transfer (excluded)";
    if (t.kind === "returned") return "Returned payment";
    if (t.kind === "loan_repayment") return "Loan repayment";
    return "";
  },
  breakdown() {
    const b = this.a?.result?.breakdown; if (!b) return [];
    return [{ label: "Income stability", value: b.stability, max: 25 }, { label: "Net margin", value: b.margin, max: 25 },
            { label: "Trend", value: b.trend, max: 15 }, { label: "Returned payments", value: b.returned, max: 15 },
            { label: "Debt burden", value: b.debt, max: 10 }, { label: "Data trust", value: b.trust, max: 10 }];
  },
  penalties() {
    const b = this.a?.result?.breakdown; if (!b) return [];
    return [{ label: "Payer concentration", value: b.concentration_penalty }, { label: "Tamper flags", value: b.tamper_penalty }]
      .filter((p) => p.value !== 0);
  },
  metricCards() {
    const r = this.a?.result; if (!r) return [];
    const m = r.metrics;
    return [
      { key: "avg_monthly_inflow", label: "Avg monthly inflow", value: this.money(m.avg_monthly_inflow) },
      { key: "avg_monthly_outflow", label: "Avg monthly outflow", value: this.money(m.avg_monthly_outflow) },
      { key: "avg_monthly_net", label: "Avg monthly net", value: this.money(m.avg_monthly_net) },
      { key: "income_cv", label: "Income volatility (CV)", value: Number(m.income_cv).toFixed(2) },
      { key: "net_margin", label: "Net margin", value: this.pct(m.net_margin) },
      { key: "trend_pct", label: "3-month trend", value: this.pct(m.trend_pct) },
      { key: "returned_count", label: "Returned payments", value: m.returned_count },
      { key: "debt_burden", label: "Debt burden", value: this.pct(m.debt_burden) },
      { key: "verified_share", label: "Verified data share", value: this.pct(m.verified_share) },
      { key: "top_payer_share", label: "Top payer share", value: m.top_payer_share === null ? "n/a" : this.pct(m.top_payer_share) },
      { key: "tamper_flag_count", label: "Tamper flags", value: m.tamper_flag_count },
      { key: "months_covered", label: "Months covered", value: m.months_covered },
      { key: "coverage_ratio", label: "Coverage ratio", value: r.coverage_ratio === null ? "n/a" : `${Number(r.coverage_ratio).toFixed(2)}×` },
    ];
  },
  highlight(key) {
    const el = document.getElementById(`metric-${key}`); if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("ring-4", "ring-indigo-400");
    setTimeout(() => el.classList.remove("ring-4", "ring-indigo-400"), 1600);
  },
  drawChart() {
    const canvas = document.getElementById("cashflow-chart");
    if (!canvas || !this.a?.result || !window.Chart) return;
    if (chart) chart.destroy();
    const rows = this.a.result.metrics.monthly;
    chart = new window.Chart(canvas, {
      data: { labels: rows.map((r) => r.month), datasets: [
        { type: "bar", label: "Inflow", data: rows.map((r) => Number(r.inflow)), backgroundColor: "#10b981" },
        { type: "bar", label: "Outflow", data: rows.map((r) => Number(r.outflow)), backgroundColor: "#f43f5e" },
        { type: "line", label: "Net", data: rows.map((r) => Number(r.net)), borderColor: "#1e293b", backgroundColor: "#1e293b", tension: 0.3 },
      ] },
      options: { responsive: true, maintainAspectRatio: false, animation: false },
    });
  },
}));

Alpine.start();
