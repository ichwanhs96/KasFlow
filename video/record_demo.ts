import { chromium, expect, type Page } from "@playwright/test";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const BASE = process.env.BASE_URL ?? "http://localhost:8080";
const KEY = process.env.DEMO_LOGIN_KEY ?? "dev-login-key";
const PACE = Number(process.env.PACE ?? "1");
const ASSETS = fileURLToPath(new URL("../demo_assets/", import.meta.url));
const Y4M = `${ASSETS}sari_buku_kas.y4m`;
const T = { timeout: 90_000 };

// BASE_PACE stretches every pause so a local stub-mode run lands near 3:20 (spec: 3:00–4:00); PACE fine-tunes.
const BASE_PACE = 1.65;
const pause = (ms: number) => new Promise((r) => setTimeout(r, ms * BASE_PACE * PACE));

async function caption(page: Page, text: string) {
  await page.evaluate((t) => {
    document.getElementById("kf-caption")?.remove();
    const d = document.createElement("div");
    d.id = "kf-caption";
    d.textContent = t;
    Object.assign(d.style, {
      position: "fixed", left: "50%", bottom: "28px", transform: "translateX(-50%)", background: "rgba(30,58,95,0.92)",
      color: "#fff", fontSize: "20px", padding: "10px 18px", borderRadius: "0", borderLeft: "3px solid #3FA37A",
      zIndex: "2147483647", maxWidth: "90%", textAlign: "center", fontFamily: "system-ui, sans-serif", pointerEvents: "none",
    });
    document.body.appendChild(d);
  }, text);
}

async function go(page: Page, path: string, text?: string) {
  await page.goto(BASE + path);
  await page.waitForLoadState("domcontentloaded");
  if (text) await caption(page, text);
}

async function main() {
  if (!existsSync(Y4M)) throw new Error(`Missing ${Y4M} — run scripts/generate_personas.py first`);
  const browser = await chromium.launch({
    args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", `--use-file-for-fake-video-capture=${Y4M}`],
    slowMo: 120,
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 }, recordVideo: { dir: "out/", size: { width: 1280, height: 720 } },
    permissions: ["camera"],
  });
  const page = await context.newPage();

  // 1 Intro
  await go(page, "/demo/intro", "KasFlow — credit signals from any data");
  await pause(12_000);

  // 2 Client applies with open-finance consent
  await go(page, "/demo/client", "A client app (PinjamCepat) calls the KasFlow API with open-finance consent");
  await pause(4_000);
  await page.getByTestId("connect-accounts").click();
  await expect(page.getByTestId("consent-modal")).toBeVisible(T);
  await pause(4_000);
  await page.getByTestId("consent-allow").click();
  await expect(page.getByTestId("kasflow-frame")).toBeVisible(T);
  await caption(page, "Open-finance data is thin: KasFlow asks for more, via an embeddable page");
  await page.getByTestId("api-log").evaluate((el) => el.scrollIntoView({ behavior: "smooth" }));
  await pause(8_000);

  // 3 Uploads inside the iframe
  const frame = page.frameLocator("#kasflow-frame");
  await caption(page, "Customer adds an e-wallet screenshot and a QRIS export — Gemini reads any format");
  await frame.getByTestId("file-input").setInputFiles(`${ASSETS}sari_dompetku.png`);
  await expect(frame.getByTestId("item-done").nth(0)).toBeVisible(T);
  await pause(3_000);
  await frame.getByTestId("file-input").setInputFiles(`${ASSETS}sari_qris.csv`);
  await expect(frame.getByTestId("item-done").nth(1)).toBeVisible(T);
  await pause(4_000);

  // 4 Camera capture of the paper ledger
  await caption(page, "No digital records? Photograph the paper cash book — Gemini reads handwriting");
  await frame.getByTestId("take-photo").click();
  await pause(3_000);
  await frame.getByTestId("capture").click();
  await expect(frame.getByTestId("item-done").nth(2)).toBeVisible(T);
  await pause(3_000);
  await frame.getByTestId("close-camera").click();
  await pause(2_000);

  // 5 Done → client notified → re-scored
  await frame.getByTestId("done").click();
  await expect(page.getByTestId("received")).toBeVisible(T);
  await caption(page, "Re-scored automatically; the client gets the result by API");
  await expect(page.getByTestId("api-log")).toContainText('"status": "scored"', T);
  await page.getByTestId("api-log").evaluate((el) => el.lastElementChild?.scrollIntoView({ behavior: "smooth" }));
  await pause(8_000);

  // 6 Console
  await go(page, `/demo-login?key=${encodeURIComponent(KEY)}`);
  await page.waitForURL("**/console**", T);
  await caption(page, "Analysts review in the KasFlow console (Google sign-in)");
  await expect(page.getByTestId("assessment-row").first()).toBeVisible(T);
  await pause(4_000);
  await page.getByTestId("assessment-row").filter({ hasText: "Sari" }).first().click();
  await expect(page.getByTestId("sources-panel")).toBeVisible(T);

  // 7 Sources
  await caption(page, "4 sources merged: verified vs AI-extracted, duplicates & transfers removed");
  await page.getByTestId("sources-panel").scrollIntoViewIfNeeded();
  await page.getByTestId("expand-source").filter({ hasText: "Bank Merapi" }).click();
  await pause(8_000);

  // 8 Result + AI summary
  await caption(page, "Deterministic score + Gemini explanation that cites its metrics");
  await page.getByTestId("score-card").scrollIntoViewIfNeeded();
  await pause(6_000);
  await page.getByTestId("ai-summary").scrollIntoViewIfNeeded();
  await pause(4_000);
  await page.getByTestId("metric-chip").first().click();
  await pause(4_000);
  await page.getByTestId("toggle-explanation").scrollIntoViewIfNeeded();
  await page.getByTestId("toggle-explanation").click();
  await pause(4_000);

  // 9 Review
  await caption(page, "Human-in-the-loop decision, fully audited");
  await page.getByTestId("review-submit").scrollIntoViewIfNeeded();
  await page.getByTestId("review-submit").click();
  await expect(page.getByTestId("review-card")).toBeVisible(T);
  await pause(5_000);

  // 10 Tamper case
  await page.getByTestId("back-to-list").click();
  await page.getByTestId("assessment-row").filter({ hasText: "Linh" }).first().click();
  await expect(page.getByTestId("tamper-badge")).toBeVisible(T);
  await caption(page, "Edited PDF? Balance arithmetic exposes tampering");
  await page.getByTestId("source-card").filter({ has: page.getByTestId("tamper-badge") }).getByTestId("expand-source").click();
  await page.getByTestId("tampered-row").first().scrollIntoViewIfNeeded();
  await pause(6_000);
  await page.getByTestId("recommendation").scrollIntoViewIfNeeded();
  await pause(4_000);

  // 11 API docs
  await go(page, "/docs", "Any company integrates via REST API");
  await pause(3_000);
  for (let i = 0; i < 4; i++) { await page.mouse.wheel(0, 350); await pause(1_200); }

  // 12 Outro
  await go(page, "/demo/outro", "Built on Gemini · Cloud Run · Firestore · Firebase");
  await pause(12_000);

  const video = page.video();
  await context.close();
  await browser.close();
  console.log(`video saved: ${await video?.path()}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
