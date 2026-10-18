import { chromium, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";

const BASE = process.env.BASE_URL ?? "http://localhost:8080";
const OUT = "out/pages/";
const PRIMARY = "rgb(59, 111, 182)";

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const errors: string[] = [];
  const watch = (p: Page) => {
    p.on("pageerror", (e) => errors.push(`${p.url()}: ${e.message}`));
    p.on("console", (m) => { if (m.type() === "error") errors.push(`${p.url()}: ${m.text()}`); });
  };
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
  watch(page);
  const shot = async (p: Page, name: string, path: string, ready: string) => {
    await p.goto(BASE + path);
    await p.waitForSelector(ready, { timeout: 30_000 });
    await p.waitForTimeout(700);
    await p.screenshot({ path: `${OUT}${name}.png`, fullPage: true });
  };

  await shot(page, "intro", "/demo/intro", "h1");
  await shot(page, "outro", "/demo/outro", "svg");
  await shot(page, "signin", "/", "#signin");
  await page.click("#signin");
  await page.waitForURL("**/console**");
  await shot(page, "console-list", "/console", "[data-testid=assessment-row]");
  await page.getByTestId("assessment-row").filter({ hasText: "Linh" }).first().click();
  await page.waitForSelector("[data-testid=tamper-badge]");
  const badges = await page.getByTestId("tamper-badge").count();
  if (badges !== 1) errors.push(`expected exactly 1 tamper-badge on Linh, found ${badges}`);
  await page.getByTestId("source-card").filter({ has: page.getByTestId("tamper-badge") }).getByTestId("expand-source").click();
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}console-detail.png`, fullPage: true });

  await shot(page, "client", "/demo/client", "[data-testid=connect-accounts]");
  const r = await page.request.post(`${BASE}/api/demo/client/apply`,
    { data: { persona: "sari", purpose: "loan", requested_amount: 50000000, tenor_months: 12 } });
  const path = new URL((await r.json()).response.body.collection_url).pathname;
  await shot(page, "collect", path, "[data-testid=take-photo]");
  const bg = await page.locator("[data-testid=done]").evaluate((el) => getComputedStyle(el).backgroundColor);
  if (bg !== PRIMARY) errors.push(`.btn-primary background is ${bg}, expected ${PRIMARY} (Tailwind preflight override?)`);

  const phone = await (await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true })).newPage();
  watch(phone);
  await shot(phone, "collect-mobile", path, "[data-testid=take-photo]");
  const overflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 0) errors.push(`collect page scrolls horizontally on a 375px phone by ${overflow}px`);

  await browser.close();
  if (errors.length) { console.error(errors.join("\n")); process.exit(1); }
  console.log(`pages OK: screenshots in video/${OUT}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
