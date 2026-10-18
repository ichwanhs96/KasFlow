import Alpine from "https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/module.esm.js";

Alpine.data("clientDemo", () => ({
  personas: [], persona: "sari", form: { purpose: "loan", requested_amount: "", tenor_months: "" },
  consentOpen: false, log: [], phase: "form", collectionUrl: "", assessmentId: null, busy: false, err: "",

  async init() {
    this.personas = (await (await fetch("/api/demo/personas")).json()).items;
    this.pick();
    window.addEventListener("message", (e) => { if (e.data?.type === "kasflow:completed") this.onCompleted(); });
  },
  get current() { return this.personas.find((p) => p.id === this.persona); },
  pick() {
    const p = this.current; if (!p) return;
    this.form = { purpose: p.purpose, requested_amount: p.requested_amount, tenor_months: p.tenor_months };
  },
  async allow() {
    this.busy = true; this.err = "";
    try {
      const r = await fetch("/api/demo/client/apply", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona: this.persona, purpose: this.form.purpose,
          requested_amount: Number(this.form.requested_amount) || null, tenor_months: Number(this.form.tenor_months) || null }),
      });
      const b = await r.json();
      if (!r.ok) throw new Error(b?.error?.message || "error");
      this.log.push(b);
      this.consentOpen = false;
      const res = b.response.body;
      if (b.response.status >= 400) throw new Error(res?.error?.message || "KasFlow API error");
      this.assessmentId = res.id;
      if (res.status === "needs_more_data") { this.collectionUrl = res.collection_url; this.phase = "collect"; }
      else this.phase = "review";
    } catch (e) { this.err = e.message; } finally { this.busy = false; }
  },
  async onCompleted() {
    if (this.phase === "received") return;
    this.phase = "received";
    for (let i = 0; i < 40; i++) {
      const b = await (await fetch(`/api/demo/assessment/${this.assessmentId}`)).json();
      this.log.push(b);
      if (b.response.body.status !== "needs_more_data") break;
      await new Promise((r) => setTimeout(r, 3000));
    }
  },
  pretty(o) { return JSON.stringify(o, null, 2); },
}));

Alpine.start();
