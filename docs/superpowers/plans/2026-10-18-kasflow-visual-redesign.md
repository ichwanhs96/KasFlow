# KasFlow Visual Redesign (Revision 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle every KasFlow page in an Interactive Brokers–like, pastel, no-emoji visual system with SVG icons and an SVG logo, then re-record the demo video. Behaviour does not change.

**Architecture:**
- Design tokens and component classes live in `app/static/css/app.css`. Tailwind (Play CDN) stays for layout utilities.
- One icon module, `app/static/js/icons.js`, returns fixed SVG strings. Alpine pages render them with `x-html`.
- The logo is a static SVG at `app/static/img/logo.svg`. It is also the favicon and is served at `/favicon.ico`.
- PinjamCepat keeps its own orange brand and only swaps emoji for SVGs.
- Every `data-testid` stays the same, so the API tests and the video script keep working.

**Tech Stack:** FastAPI static pages, Alpine.js 3.14.1, Tailwind Play CDN, Chart.js 4.4.1, Playwright 1.48.2 (video and page checks), pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-kasflow-design.md`. The visual system is §9.0. §9.2–9.5, §11, §13 and §14 were updated in revision 2.

## Global Constraints

- **No emoji anywhere** in the UI, the intro and outro cards, video captions, README, SUBMISSION.md or the pitch outline. **Exception:** country flag emoji (🇮🇩 🇵🇭 🇻🇳).
- **Palette (exact):**

  | Token | Value |
  |---|---|
  | `--bg` | `#F5F7FA` |
  | `--panel` | `#FFFFFF` |
  | `--border` | `#D9DEE7` |
  | `--strip` | `#EEF2F7` |
  | `--topbar` | `#E3ECF8` |
  | `--ink` | `#1F2A37` |
  | `--muted` | `#667085` |
  | `--primary` | `#3B6FB6`, hover `#2F5C99` |
  | pos (bg / ink / line) | `#E3F4EA` / `#1F6B45` / `#B7E0C7` |
  | neg (bg / ink / line) | `#FBE7E6` / `#A23B32` / `#F2C2BE` |
  | warn (bg / ink / line) | `#FDF1DC` / `#8A5A12` / `#F2D9A8` |
  | info (bg / ink / line) | `#E6EEF9` / `#2F5C99` / `#C3D5EE` |
  | chart | inflow `#8CCFA8`, outflow `#F2A7A0`, net `#3B6FB6` |

- **Shape and type:** radius 2 px, no shadows, no gradients. System UI font at a 13 px base. `tabular-nums` for numbers.
- **Logo:** blue bars `#4A7FC1`, green flow line `#3FA37A`, wordmark "Kas" `#1E3A5F` + "Flow" `#2E8B62`. Tagline "Credit signals from any data".
- **Icon set (exact names):** `bank`, `wallet`, `document`, `camera`, `plug`, `upload`, `warning`, `check`, `cross`, `chevron`, `signout`, `clock`. 16 px, stroke 1.5, `currentColor`. Use `x-html` only with these fixed strings.
- **No new frontend dependency.**
- **Keep every existing `data-testid` and every user-facing string the tests assert:**
  - "Sign in with Google", "Data diterima", "US$2.5 trillion", "Cloud Run", "signInCustom"
  - the i18n strings
- **Terminology:** never "borrower" or "lender".
- **Commits:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Commands:** run from the repo root `/Users/ichone/Documents/projects/hackathon/kasflow`. Tests: `.venv/bin/pytest`.

## Review Focus

1. **Long text in the rigid layout.** Long customer names, AI summary text and failed-item messages must wrap, with no horizontal page scroll on a 375 px phone. Pinned in Task 5 (`check_pages.ts`: the mobile collect page asserts `scrollWidth <= innerWidth`).
2. **Tailwind preflight overriding component classes.** `.btn-primary` must keep its blue background after Tailwind injects its styles. Pinned in Task 5 (`check_pages.ts` asserts the computed background `rgb(59, 111, 182)`).
3. **Unknown icon names.** `icon()` gets a name it doesn't know. It must fall back to a fixed icon and never echo the name into markup (XSS hygiene). Pinned in Task 1 (`test_icon_unknown_name_falls_back`).
4. **Tamper label on clean sources.** It must not exist in the DOM at all (the video's strict locators depend on it). Pinned in Task 5 (`check_pages.ts` asserts exactly one `tamper-badge` on Linh).
5. **Console errors after the restyle.** No page may log a console error, for example from a broken Alpine expression. Pinned in Task 5 (`check_pages.ts` fails on any console or page error).

---

### Task 1: Foundation: tokens, icons, logo, favicon

**Files:**
- Create: `app/static/img/logo.svg`, `app/static/js/icons.js`, `tests/test_design.py`
- Replace: `app/static/css/app.css`
- Modify: `app/routers/pages.py` (add the `/favicon.ico` route)

**Interfaces:**
- Produces:
  - `icons.js`:
    - `export const ICON_NAMES: string[]`
    - `export function icon(name: string, size = 16): string`, which returns an `<svg>` string and falls back to `document` for unknown names
  - CSS classes:
    - layout: `.kf`, `.topbar`, `.wrap`, `.brand`, `.wordmark .kas/.flow`, `.tagline`, `.tabs`, `.tab(.active)`
    - panels and tables: `.panel`, `.panel-h`, `.panel-b`, `.tbl` (`.r`, `tr.clickable`, `tr.row-neg`, `tr.row-dim`)
    - controls: `.btn`, `.btn-primary`, `.field`, `.label` plus `.label-pos/-neg/-warn/-info/-muted`, `.seg` (`button.on`)
    - data display: `.kv`, `.metric` (`.k`, `.v`, `.hl`), `.bar>i`, `.scale` (`>i`, `>b`), `.fill-pos/-warn/-neg/-muted`, `.num`
    - other: `.tile`, `.ico`, `.spinner`, `[x-cloak]`
  - `GET /favicon.ico` returns `logo.svg` as `image/svg+xml`

- [ ] **Step 1: Write the failing tests**

`tests/test_design.py`:
```python
import re
import shutil
import subprocess

import pytest

from app.config import ROOT, STATIC_DIR

SPEC_ICONS = {"bank", "wallet", "document", "camera", "plug", "upload", "warning", "check", "cross", "chevron",
              "signout", "clock"}


def icon_names() -> set[str]:
    src = (STATIC_DIR / "js" / "icons.js").read_text(encoding="utf-8")
    body = src.split("const PATHS = {", 1)[1].split("};", 1)[0]
    return set(re.findall(r"^\s+(\w+):", body, re.M))


def test_icon_set_matches_spec():
    assert SPEC_ICONS <= icon_names()


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_icon_unknown_name_falls_back():
    js = ("import { icon, ICON_NAMES } from './app/static/js/icons.js';"
          "const s = icon('<img onerror=x>');"
          "if (s.includes('onerror') || !s.startsWith('<svg') || s !== icon('document')) process.exit(1);"
          "if (!icon('bank', 24).includes('width=\"24\"') || ICON_NAMES.length < 12) process.exit(2);")
    r = subprocess.run(["node", "--input-type=module", "-e", js], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_logo_and_favicon_served(client):
    r = client.get("/static/img/logo.svg")
    assert r.status_code == 200 and "<svg" in r.text and "#4A7FC1" in r.text and "#3FA37A" in r.text
    f = client.get("/favicon.ico")
    assert f.status_code == 200 and f.headers["content-type"].startswith("image/svg+xml")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_design.py`
Expected: FAIL (`FileNotFoundError` for `icons.js`; 404 for the logo).

- [ ] **Step 3: Write the logo, icons and CSS, and add the favicon route**

`app/static/img/logo.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" role="img" aria-label="KasFlow">
  <rect x="0.5" y="0.5" width="23" height="23" rx="2" fill="#E3ECF8" stroke="#C3D5EE"/>
  <rect x="5" y="14" width="3.2" height="6" fill="#4A7FC1"/>
  <rect x="10.4" y="11" width="3.2" height="9" fill="#4A7FC1"/>
  <rect x="15.8" y="8" width="3.2" height="12" fill="#4A7FC1"/>
  <polyline points="4.5,11.5 9.5,8.6 14.8,6.2 19.6,3.6" fill="none" stroke="#3FA37A" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
  <polyline points="17.1,3.2 19.6,3.6 18.9,6" fill="none" stroke="#3FA37A" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

`app/static/js/icons.js`:
```javascript
// Inline SVG icons (spec §9.0). Fixed strings only: never interpolate user or model data into them.
const PATHS = {
  bank: '<path d="M3 9.5 12 4l9 5.5"/><path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8"/><path d="M3 20h18"/>',
  wallet: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/><path d="M16 14.5h2"/>',
  document: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M10 13h6M10 17h6"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
  plug: '<path d="M9 3v5M15 3v5"/><path d="M6 8h12v3a6 6 0 0 1-12 0z"/><path d="M12 17v4"/>',
  upload: '<path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M4 16v4h16v-4"/>',
  warning: '<path d="M12 3 2 20h20z"/><path d="M12 10v4"/><path d="M12 17.5v.5"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7"/>',
  cross: '<path d="M6 6l12 12M18 6 6 18"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  signout: '<path d="M14 4h5v16h-5"/><path d="M10 8l-4 4 4 4"/><path d="M6 12h10"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
};

export const ICON_NAMES = Object.keys(PATHS);

export function icon(name, size = 16) {
  const d = PATHS[name] || PATHS.document;
  const px = Number(size) || 16;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${px}" height="${px}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
}
```

`app/static/css/app.css`:
```css
/* KasFlow visual system (spec §9.0): IB-like, pastel, rigid. Tailwind is used for layout utilities only. */
:root {
  --bg: #F5F7FA; --panel: #FFFFFF; --border: #D9DEE7; --strip: #EEF2F7; --topbar: #E3ECF8;
  --ink: #1F2A37; --muted: #667085; --primary: #3B6FB6; --primary-hover: #2F5C99;
  --pos-bg: #E3F4EA; --pos-ink: #1F6B45; --pos-line: #B7E0C7;
  --neg-bg: #FBE7E6; --neg-ink: #A23B32; --neg-line: #F2C2BE;
  --warn-bg: #FDF1DC; --warn-ink: #8A5A12; --warn-line: #F2D9A8;
  --info-bg: #E6EEF9; --info-ink: #2F5C99; --info-line: #C3D5EE;
}
[x-cloak] { display: none !important; }
body.kf { background: var(--bg); color: var(--ink); font: 13px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.num { font-variant-numeric: tabular-nums; }

.topbar { background: var(--topbar); border-bottom: 2px solid var(--primary); }
.topbar .wrap { max-width: 1200px; margin: 0 auto; padding: 0 16px; height: 44px; display: flex; align-items: center; gap: 20px; }
.brand { display: flex; align-items: center; gap: 8px; }
.brand img { width: 24px; height: 24px; }
.wordmark { font-weight: 600; font-size: 15px; letter-spacing: .01em; }
.wordmark .kas { color: #1E3A5F; }
.wordmark .flow { color: #2E8B62; }
.tagline { color: var(--muted); font-size: 12px; }
.tabs { display: flex; align-self: stretch; }
.tab { display: flex; align-items: center; padding: 0 12px; color: #1E3A5F; font-weight: 500; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab:hover { background: rgba(255, 255, 255, .5); }
.tab.active { border-bottom-color: #1E3A5F; font-weight: 600; }

.panel { background: var(--panel); border: 1px solid var(--border); border-radius: 2px; }
.panel-h { background: var(--strip); border-bottom: 1px solid var(--border); padding: 6px 10px; min-height: 32px; display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: #344054; }
.panel-h .plain { text-transform: none; letter-spacing: normal; font-weight: 400; color: var(--muted); }
.panel-b { padding: 10px; }

.tbl { width: 100%; border-collapse: collapse; }
.tbl th { background: var(--strip); text-align: left; font-weight: 600; font-size: 11px; color: #475467; padding: 5px 8px; border-bottom: 1px solid var(--border); position: sticky; top: 0; white-space: nowrap; }
.tbl td { padding: 5px 8px; border-bottom: 1px solid #EEF1F5; height: 28px; vertical-align: middle; }
.tbl tbody tr:nth-child(even) td { background: #FAFBFC; }
.tbl .r { text-align: right; font-variant-numeric: tabular-nums; }
.tbl tr.clickable { cursor: pointer; }
.tbl tr.clickable:hover td { background: var(--info-bg); }
.tbl tr.row-neg td { background: var(--neg-bg) !important; color: var(--neg-ink); }
.tbl tr.row-dim td { color: #98A2B3; }

.btn { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 12px; border: 1px solid #C5CCD8; background: #fff; color: var(--ink); border-radius: 2px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap; }
.btn:hover { background: var(--strip); }
.btn-primary { background: var(--primary); border-color: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-hover); }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.field { border: 1px solid #C5CCD8; border-radius: 2px; min-height: 30px; padding: 0 8px; background: #fff; color: var(--ink); }
.field:focus { outline: 2px solid var(--info-line); outline-offset: 0; }

.label { display: inline-flex; align-items: center; gap: 4px; padding: 1px 6px; font-size: 11px; font-weight: 600; line-height: 18px; border-left: 3px solid #98A2B3; border-radius: 2px; background: var(--strip); color: #475467; white-space: nowrap; }
.label-pos { background: var(--pos-bg); color: var(--pos-ink); border-left-color: var(--pos-ink); }
.label-neg { background: var(--neg-bg); color: var(--neg-ink); border-left-color: var(--neg-ink); }
.label-warn { background: var(--warn-bg); color: var(--warn-ink); border-left-color: var(--warn-ink); }
.label-info { background: var(--info-bg); color: var(--info-ink); border-left-color: var(--info-ink); }
.label-muted { background: var(--strip); color: #475467; border-left-color: #98A2B3; }
button.label { cursor: pointer; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 500; }
button.label:hover { filter: brightness(.97); }

.seg { display: inline-flex; border: 1px solid #C5CCD8; border-radius: 2px; overflow: hidden; text-transform: none; letter-spacing: normal; }
.seg button { padding: 3px 10px; font-size: 12px; font-weight: 500; background: #fff; color: var(--ink); border-right: 1px solid #C5CCD8; }
.seg button:last-child { border-right: 0; }
.seg button.on { background: var(--info-bg); color: var(--info-ink); font-weight: 600; }

.kv dt { color: var(--muted); font-size: 11px; }
.kv dd { font-weight: 600; font-variant-numeric: tabular-nums; }
.metric { background: #fff; border: 1px solid var(--border); border-radius: 2px; padding: 8px 10px; transition: outline-color .2s; outline: 2px solid transparent; }
.metric .k { color: var(--muted); font-size: 11px; }
.metric .v { font-size: 16px; font-weight: 600; font-variant-numeric: tabular-nums; }
.metric.hl { outline-color: var(--primary); }
.bar { height: 4px; background: #EEF1F5; }
.bar > i { display: block; height: 4px; background: var(--primary); }
.scale { position: relative; height: 8px; background: #EEF1F5; border: 1px solid var(--border); }
.scale > i { position: absolute; left: 0; top: 0; bottom: 0; }
.scale > b { position: absolute; top: -3px; bottom: -3px; width: 1px; background: #98A2B3; }
.fill-pos { background: #8CCFA8; } .fill-warn { background: #F2D9A8; } .fill-neg { background: #F2A7A0; } .fill-muted { background: #D0D5DD; }

.tile { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; width: 100%; padding: 18px 8px; border: 1px solid #C5CCD8; border-radius: 2px; background: #fff; color: #1E3A5F; font-weight: 600; text-align: center; cursor: pointer; }
.tile:hover { background: var(--info-bg); border-color: var(--info-line); }
.ico { display: inline-flex; flex: none; vertical-align: -3px; }
.spinner { display: inline-block; width: .85rem; height: .85rem; border: 2px solid var(--border); border-top-color: var(--primary); border-radius: 9999px; animation: spin 1s linear infinite; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }
```

In `app/routers/pages.py`, add after the `index()` route:
```python
@router.get("/favicon.ico")
def favicon():
    return FileResponse(STATIC_DIR / "img" / "logo.svg", media_type="image/svg+xml")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_design.py && .venv/bin/pytest`
Expected: `3 passed`, then the full suite passes.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(ui): add design tokens, SVG icon set, logo and favicon

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Sign-in page, demo login and analyst console

**Files:**
- Replace: `app/static/index.html`, `app/static/console.html`, `app/static/js/console.js`
- Modify: `app/static/demo/login.html` (add the favicon link)

**Interfaces:**
- Consumes: `icon()` from Task 1 and the CSS classes from Task 1
- Produces: the same `data-testid` hooks as before, namely:
  - `assessment-row`, `back-to-list`, `status-chip`, `collection-card`, `score-now`
  - `sources-panel`, `source-card`, `expand-source`, `tamper-badge`, `tampered-row`, `txn-row`
  - `score-card`, `recommendation`, `ai-summary`, `metric-chip`, `toggle-explanation`
  - `review-panel`, `review-override`, `review-submit`, `review-card`, `regen-summary`
  
  Plus Alpine methods `icon(name, size)`, `kindIcon(kind) -> icon name`, `statusClass`, `recClass` and `gradeFill` (these return CSS class names).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_design.py`:
```python
def test_console_and_signin_use_the_design_system(client):
    c = client.get("/console").text
    assert 'class="topbar"' in c and 'src="/static/img/logo.svg"' in c and "x-html=\"icon(" in c
    assert 'rel="icon" href="/static/img/logo.svg"' in c
    i = client.get("/").text
    assert 'class="topbar"' in i and "Sign in with Google" in i and 'rel="icon" href="/static/img/logo.svg"' in i
    js = client.get("/static/js/console.js").text
    assert 'from "/static/js/icons.js"' in js and "label-pos" in js
    assert 'rel="icon" href="/static/img/logo.svg"' in client.get("/demo-login").text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_design.py::test_console_and_signin_use_the_design_system`
Expected: FAIL (`assert 'class="topbar"' in c`).

- [ ] **Step 3: Write the pages**

`app/static/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>KasFlow Console</title>
  <link rel="icon" href="/static/img/logo.svg" type="image/svg+xml">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="/static/css/app.css">
  <script src="/config.js"></script>
</head>
<body class="kf min-h-screen flex flex-col">
  <header class="topbar">
    <div class="wrap">
      <span class="brand"><img src="/static/img/logo.svg" alt=""><span class="wordmark"><span class="kas">Kas</span><span class="flow">Flow</span></span></span>
      <span class="tagline">Credit signals from any data</span>
    </div>
  </header>
  <main class="flex-1 flex items-center justify-center p-4">
    <div class="panel w-full max-w-sm">
      <div class="panel-h"><span>Analyst console</span></div>
      <div class="panel-b space-y-3">
        <p class="text-slate-600">Sign in to review credit assessments.</p>
        <button id="signin" class="btn w-full justify-center h-9">
          <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.1C12.5 13.6 17.8 9.5 24 9.5z"/><path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.7 6c4.5-4.2 6.9-10.3 6.9-17.7z"/><path fill="#FBBC05" d="M10.6 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.7 10.7l7.9-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.7-6c-2.1 1.4-4.9 2.3-8.2 2.3-6.2 0-11.5-4.1-13.4-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z"/></svg>
          <span id="signin-label">Sign in with Google</span>
        </button>
        <p id="err" class="text-[12px] text-[color:var(--neg-ink)]"></p>
        <p class="text-[12px] text-slate-500 border-t border-[color:var(--border)] pt-3">Demo mode: any Google account can sign in as an analyst.
          Customer collection pages need no login. Try the <a class="underline" href="/demo/client">demo client app</a>.</p>
      </div>
    </div>
  </main>
  <script type="module">
    import { signInGoogle, currentUser, authMode } from "/static/js/firebase.js";
    const btn = document.getElementById("signin");
    if (authMode === "stub") document.getElementById("signin-label").textContent = "Sign in with Google (dev stub)";
    if (await currentUser()) location.href = "/console";
    btn.onclick = async () => {
      try { await signInGoogle(); location.href = "/console"; }
      catch (e) { document.getElementById("err").textContent = e.message; }
    };
  </script>
</body>
</html>
```

`app/static/js/console.js`:
```javascript
import Alpine from "https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/module.esm.js";
import { api, currentUser, signOut } from "/static/js/firebase.js";
import { icon as svgIcon } from "/static/js/icons.js";

const FLAGS = { ID: "🇮🇩", PH: "🇵🇭", VN: "🇻🇳" };
const LOCALE = { ID: "id-ID", PH: "en-PH", VN: "vi-VN" };
const STATUS = { created: "Created", needs_more_data: "Needs more data", scored: "Scored", reviewed: "Reviewed", error: "Error" };
const KIND_ICON = { open_finance: "bank", api_push: "plug", upload: "document", camera: "camera" };
const STATUS_CLASS = { needs_more_data: "label-warn", scored: "label-info", reviewed: "label-pos", error: "label-neg" };
const REC_CLASS = { favorable: "label-pos", review: "label-warn", unfavorable: "label-neg" };
const GRADE_FILL = { A: "fill-pos", B: "fill-pos", C: "fill-warn", D: "fill-neg" };
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

  icon(name, size) { return svgIcon(name, size); },
  flag(c) { return FLAGS[c] || ""; },
  kindIcon(k) { return KIND_ICON[k] || "document"; },
  statusLabel(s) { return STATUS[s] || s; },
  statusClass(s) { return STATUS_CLASS[s] || "label-muted"; },
  recClass(r) { return REC_CLASS[r] || "label-muted"; },
  gradeFill() { return GRADE_FILL[this.a?.result?.grade] || "fill-muted"; },
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
    if (t.tampered) return "row-neg";
    if (t.duplicate_of || t.kind === "internal_transfer") return "row-dim";
    return "";
  },
  rowNote(t, s) {
    if (t.tampered) {
      const f = s.tamper_flags.find((x) => x.row_index === t.row_index);
      return `Balance mismatch: expected ${this.money(f?.expected_balance)}`;
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
    el.classList.add("hl");
    setTimeout(() => el.classList.remove("hl"), 1600);
  },
  drawChart() {
    const canvas = document.getElementById("cashflow-chart");
    if (!canvas || !this.a?.result || !window.Chart) return;
    if (chart) chart.destroy();
    const rows = this.a.result.metrics.monthly;
    const axis = { grid: { color: "#EEF1F5" }, ticks: { color: "#667085", font: { size: 11 } } };
    chart = new window.Chart(canvas, {
      data: { labels: rows.map((r) => r.month), datasets: [
        { type: "bar", label: "Inflow", data: rows.map((r) => Number(r.inflow)), backgroundColor: "#8CCFA8" },
        { type: "bar", label: "Outflow", data: rows.map((r) => Number(r.outflow)), backgroundColor: "#F2A7A0" },
        { type: "line", label: "Net", data: rows.map((r) => Number(r.net)), borderColor: "#3B6FB6", backgroundColor: "#3B6FB6", borderWidth: 1.5, pointRadius: 2, tension: 0 },
      ] },
      options: { responsive: true, maintainAspectRatio: false, animation: false,
        plugins: { legend: { labels: { boxWidth: 10, color: "#344054", font: { size: 11 } } } },
        scales: { x: axis, y: axis } },
    });
  },
}));

Alpine.start();
```

`app/static/console.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>KasFlow Console</title>
  <link rel="icon" href="/static/img/logo.svg" type="image/svg+xml">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <link rel="stylesheet" href="/static/css/app.css">
  <script src="/config.js"></script>
  <script type="module" src="/static/js/console.js"></script>
</head>
<body class="kf">
<div x-data="consoleApp" x-cloak class="min-h-screen">
  <header class="topbar">
    <div class="wrap">
      <a href="#list" class="brand"><img src="/static/img/logo.svg" alt=""><span class="wordmark"><span class="kas">Kas</span><span class="flow">Flow</span></span></a>
      <nav class="tabs">
        <a href="#list" class="tab active">Assessments</a>
        <a href="/docs" target="_blank" class="tab">API docs</a>
      </nav>
      <span class="tagline hidden lg:inline">Credit signals from any data</span>
      <div class="ml-auto flex items-center gap-3 min-w-0">
        <span class="truncate text-[12px] text-slate-600" x-text="user?.email"></span>
        <button @click="logout()" class="btn"><span class="ico" x-html="icon('signout')"></span><span class="hidden sm:inline">Sign out</span></button>
      </div>
    </div>
  </header>

  <main class="max-w-[1200px] mx-auto px-4 py-4 space-y-3">
    <div x-show="error" class="label label-neg whitespace-normal w-full py-1" x-text="error"></div>

    <!-- LIST -->
    <section x-show="route==='list'" class="panel">
      <div class="panel-h"><span>Assessments</span>
        <div class="seg">
          <template x-for="f in filters" :key="f.key">
            <button @click="filter=f.key" :class="filter===f.key ? 'on' : ''" x-text="f.label"></button>
          </template>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="tbl">
          <thead><tr><th>Customer</th><th>Type</th><th>Country</th><th>Purpose</th><th>Status</th>
            <th class="r">Score</th><th>Grade</th><th>Recommendation</th><th class="r">Updated</th></tr></thead>
          <tbody>
            <template x-for="row in filtered" :key="row.id">
              <tr data-testid="assessment-row" class="clickable" @click="location.hash = '#a/' + row.id">
                <td class="font-semibold" x-text="row.customer.name"></td>
                <td class="text-slate-500" x-text="row.customer.type"></td>
                <td class="whitespace-nowrap"><span x-text="flag(row.customer.country)"></span> <span x-text="row.customer.country"></span></td>
                <td x-text="row.purpose"></td>
                <td><span class="label" :class="statusClass(row.status)" x-text="statusLabel(row.status)"></span></td>
                <td class="r" x-text="row.score === null ? '—' : row.score"></td>
                <td x-text="row.grade || '—'"></td>
                <td><span x-show="row.final_recommendation || row.recommendation" class="label"
                  :class="recClass(row.final_recommendation || row.recommendation)" x-text="row.final_recommendation || row.recommendation"></span></td>
                <td class="r text-slate-500" x-text="ago(row.updated_at)"></td>
              </tr>
            </template>
            <tr x-show="filtered.length === 0"><td colspan="9" class="text-center text-slate-500 py-6">No assessments yet.
              Create one from the <a class="underline" href="/demo/client" target="_blank">demo client app</a> or the
              <a class="underline" href="/docs" target="_blank">API</a>.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- DETAIL -->
    <section x-show="route==='detail'" class="space-y-3">
      <a href="#list" data-testid="back-to-list" class="inline-flex items-center gap-1 text-[12px] text-[color:var(--primary)]">&larr; All assessments</a>
      <template x-if="a">
        <div class="space-y-3">
          <div class="panel">
            <div class="panel-h"><span>Assessment</span>
              <span data-testid="status-chip" class="label" :class="statusClass(a.status)" x-text="statusLabel(a.status)"></span></div>
            <div class="panel-b grid lg:grid-cols-[1fr_auto] gap-3">
              <div class="min-w-0">
                <div class="text-[18px] font-semibold break-words" x-text="a.customer.name"></div>
                <div class="text-slate-600"><span x-text="flag(a.customer.country)"></span> <span x-text="a.customer.country"></span> ·
                  <span x-text="a.customer.type"></span> · <span x-text="a.customer.occupation_or_business_type"></span> ·
                  <span x-text="a.customer.years_active + ' yrs active'"></span></div>
                <div class="text-[12px] text-slate-500 mt-1">Consent <span class="font-mono" x-text="a.consent.ref"></span> via
                  <span x-text="a.consent.provider"></span>, valid until <span x-text="dateStr(a.consent.expires_at)"></span></div>
              </div>
              <dl class="kv grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-1">
                <div><dt>Purpose</dt><dd x-text="a.purpose"></dd></div>
                <div><dt>Requested</dt><dd x-text="a.requested_amount ? money(a.requested_amount) : '—'"></dd></div>
                <div><dt>Tenor</dt><dd x-text="a.tenor_months ? a.tenor_months + ' months' : '—'"></dd></div>
                <div><dt>Data coverage</dt><dd x-text="(a.sufficiency?.months_covered ?? 0) + '/6 mo · ' + (a.sufficiency?.inflow_txn_count ?? 0) + '/20 in'"></dd></div>
              </dl>
            </div>
            <template x-if="a.sufficiency?.reasons?.length">
              <div class="px-[10px] pb-2 flex flex-wrap gap-2"><template x-for="r in a.sufficiency.reasons"><span class="label label-warn whitespace-normal" x-text="r"></span></template></div>
            </template>
          </div>

          <div x-show="a.status === 'needs_more_data'" data-testid="collection-card" class="panel">
            <div class="panel-h"><span>More data needed</span></div>
            <div class="panel-b space-y-3">
              <p class="text-slate-600">Send the customer a secure collection link (no login, expires in 72 hours) or embed it in your app.</p>
              <div class="flex flex-wrap gap-2">
                <button @click="genLink()" :disabled="!!busy" class="btn btn-primary">Generate link</button>
                <button @click="scoreNow()" :disabled="!!busy" class="btn" data-testid="score-now">Score now with available data</button>
              </div>
              <template x-if="link">
                <div class="flex flex-wrap gap-4 items-start">
                  <div class="w-36 h-36 border border-[color:var(--border)] p-1 bg-white" x-html="link.qr_svg"></div>
                  <div class="space-y-2 min-w-0 flex-1">
                    <input readonly class="field w-full font-mono text-[12px]" :value="link.collection_url">
                    <button class="btn" @click="navigator.clipboard.writeText(link.collection_url)">Copy link</button>
                    <div class="text-[12px] text-slate-500">Expires <span x-text="dateStr(link.collection_expires_at)"></span></div>
                  </div>
                </div>
              </template>
              <table class="tbl" x-show="a.collection?.items?.length">
                <thead><tr><th>Item</th><th>Status</th><th class="r">Transactions</th></tr></thead>
                <tbody>
                  <template x-for="it in (a.collection?.items || [])"><tr>
                    <td class="break-all" x-text="it.filename"></td>
                    <td><span class="label" :class="it.status === 'done' ? 'label-pos' : 'label-neg'"><span class="ico" x-html="icon(it.status === 'done' ? 'check' : 'cross')"></span><span x-text="it.status"></span></span></td>
                    <td class="r" x-text="it.txn_count"></td></tr></template>
                </tbody>
              </table>
            </div>
          </div>

          <div class="panel" data-testid="sources-panel">
            <div class="panel-h"><span x-text="'Data sources (' + a.sources.length + ')'"></span></div>
            <div class="divide-y divide-[color:var(--border)]">
              <template x-for="s in a.sources" :key="s.id">
                <div data-testid="source-card">
                  <button class="w-full flex flex-wrap items-center gap-x-3 gap-y-1 px-[10px] py-2 text-left hover:bg-[color:var(--strip)]"
                          data-testid="expand-source" @click="expanded[s.id] = !expanded[s.id]">
                    <span class="ico text-[color:var(--primary)]" x-html="icon(kindIcon(s.kind))"></span>
                    <span class="font-semibold" x-text="s.label"></span>
                    <span class="label" :class="s.trust === 'verified' ? 'label-pos' : 'label-warn'" x-text="s.trust === 'verified' ? 'Verified' : 'Extracted by AI'"></span>
                    <span class="text-[12px] text-slate-500 num" x-text="s.txn_count + ' txns · ' + s.months_covered + ' months'"></span>
                    <template x-if="s.tamper_flags.length">
                      <span data-testid="tamper-badge" class="label label-neg"><span class="ico" x-html="icon('warning')"></span><span x-text="s.tamper_flags.length + ' balance mismatches'"></span></span>
                    </template>
                    <span class="ml-auto ico text-slate-500 transition-transform" :class="expanded[s.id] ? 'rotate-180' : ''" x-html="icon('chevron')"></span>
                  </button>
                  <div x-show="expanded[s.id]" class="overflow-auto max-h-96 border-t border-[color:var(--border)]">
                    <table class="tbl">
                      <thead><tr><th>Date</th><th>Description</th><th class="r">Amount</th><th class="r">Balance</th><th>Note</th></tr></thead>
                      <tbody>
                        <template x-for="t in sourceTxns(s.id)" :key="t.id">
                          <tr :class="rowClass(t)" :data-testid="t.tampered ? 'tampered-row' : 'txn-row'">
                            <td class="whitespace-nowrap num" x-text="t.date"></td>
                            <td x-text="t.description"></td>
                            <td class="r whitespace-nowrap" :class="t.direction === 'in' ? 'text-[color:var(--pos-ink)]' : 'text-[color:var(--neg-ink)]'"
                                x-text="(t.direction === 'in' ? '+' : '−') + money(t.amount)"></td>
                            <td class="r whitespace-nowrap" x-text="t.balance === null ? '' : money(t.balance)"></td>
                            <td><span x-show="rowNote(t, s)" class="label" :class="t.tampered ? 'label-neg' : 'label-muted'" x-text="rowNote(t, s)"></span></td>
                          </tr>
                        </template>
                      </tbody>
                    </table>
                  </div>
                </div>
              </template>
              <p x-show="a.sources.length === 0" class="px-[10px] py-3 text-slate-500">No data sources yet.</p>
            </div>
          </div>

          <div x-show="a.result" class="grid lg:grid-cols-[340px_1fr] gap-3">
            <div class="panel" data-testid="score-card">
              <div class="panel-h"><span>Score</span><span class="plain">Deterministic engine</span></div>
              <div class="panel-b space-y-3">
                <div class="flex items-end gap-3">
                  <div class="text-[40px] leading-none font-semibold num" x-text="a.result?.score"></div>
                  <div class="pb-1"><div class="text-[11px] text-slate-500">of 100</div><div class="font-semibold" x-text="'Grade ' + (a.result?.grade || '')"></div></div>
                  <span data-testid="recommendation" class="label ml-auto mb-1 text-[12px]" :class="recClass(a.result?.recommendation)" x-text="a.result?.recommendation"></span>
                </div>
                <div class="scale"><i :class="gradeFill()" :style="`width:${a.result?.score || 0}%`"></i><b style="left:50%"></b><b style="left:65%"></b><b style="left:80%"></b></div>
                <div class="relative h-3 text-[10px] text-slate-500 num">
                  <span class="absolute left-0">0</span>
                  <span class="absolute -translate-x-1/2" style="left:50%">50</span>
                  <span class="absolute -translate-x-1/2" style="left:65%">65</span>
                  <span class="absolute -translate-x-1/2" style="left:80%">80</span>
                  <span class="absolute right-0">100</span>
                </div>
                <div class="flex flex-wrap gap-2">
                  <span x-show="a.result?.limited_data" class="label label-warn">Limited data</span>
                  <span x-show="a.result?.metrics?.tamper_flag_count > 0" class="label label-neg">Tamper flags</span>
                </div>
                <table class="tbl">
                  <thead><tr><th>Component</th><th class="r">Points</th><th style="width:38%"></th></tr></thead>
                  <tbody>
                    <template x-for="b in breakdown()"><tr><td x-text="b.label"></td><td class="r" x-text="b.value + ' / ' + b.max"></td>
                      <td><div class="bar"><i :style="`width:${Math.max(0, b.value) / b.max * 100}%`"></i></div></td></tr></template>
                    <template x-for="p in penalties()"><tr><td class="text-[color:var(--neg-ink)]" x-text="p.label"></td>
                      <td class="r text-[color:var(--neg-ink)]" x-text="p.value"></td><td></td></tr></template>
                  </tbody>
                </table>
              </div>
            </div>
            <div class="space-y-3 min-w-0">
              <div class="panel">
                <div class="panel-h"><span>Key metrics</span></div>
                <div class="panel-b grid sm:grid-cols-2 xl:grid-cols-4 gap-2">
                  <template x-for="m in metricCards()" :key="m.key">
                    <div :id="'metric-' + m.key" class="metric"><div class="k" x-text="m.label"></div><div class="v" x-text="m.value"></div></div>
                  </template>
                </div>
                <div class="border-t border-[color:var(--border)] px-[10px] py-2 flex flex-wrap gap-x-6 gap-y-1">
                  <span class="text-slate-500">Affordability</span>
                  <span>Max monthly commitment <b class="num" x-text="money(a.result?.max_monthly_commitment)"></b></span>
                  <template x-if="a.result?.installment"><span>Installment <b class="num" x-text="money(a.result.installment)"></b></span></template>
                  <template x-if="a.result?.suggested_max_amount"><span>Suggested max amount <b class="num" x-text="money(a.result.suggested_max_amount)"></b></span></template>
                </div>
              </div>
              <div class="panel">
                <div class="panel-h"><span>Monthly cash flow</span></div>
                <div class="panel-b"><div class="h-56"><canvas id="cashflow-chart"></canvas></div></div>
              </div>
            </div>
          </div>

          <div x-show="a.result" class="panel" data-testid="ai-summary">
            <div class="panel-h"><span>AI summary</span><span class="plain">Drafted by Gemini. The analyst reviews before acting.</span></div>
            <template x-if="a.result?.ai_summary">
              <div class="panel-b space-y-3">
                <div class="text-[15px] font-semibold" x-text="a.result.ai_summary.headline"></div>
                <p x-text="a.result.ai_summary.summary"></p>
                <div class="grid md:grid-cols-2 gap-4">
                  <div>
                    <div class="text-[11px] font-semibold uppercase tracking-wider text-[color:var(--pos-ink)] mb-1">Strengths</div>
                    <ul class="space-y-1"><template x-for="p in a.result.ai_summary.strengths"><li class="flex gap-2 items-start">
                      <span class="ico text-[color:var(--pos-ink)] mt-[2px]" x-html="icon('check')"></span>
                      <span><span x-text="p.point"></span> <button class="label label-info" data-testid="metric-chip" @click="highlight(p.metric)" x-text="p.metric"></button></span></li></template></ul>
                  </div>
                  <div>
                    <div class="text-[11px] font-semibold uppercase tracking-wider text-[color:var(--neg-ink)] mb-1">Risks</div>
                    <ul class="space-y-1"><template x-for="p in a.result.ai_summary.risks"><li class="flex gap-2 items-start">
                      <span class="ico text-[color:var(--neg-ink)] mt-[2px]" x-html="icon('warning')"></span>
                      <span><span x-text="p.point"></span> <button class="label label-info" data-testid="metric-chip" @click="highlight(p.metric)" x-text="p.metric"></button></span></li></template></ul>
                  </div>
                </div>
                <div class="grid md:grid-cols-2 gap-4">
                  <div><div class="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1">Data notes</div>
                    <ul class="list-disc pl-5 space-y-1"><template x-for="n in a.result.ai_summary.data_notes"><li x-text="n"></li></template></ul></div>
                  <div><div class="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1">Next steps</div>
                    <ul class="list-disc pl-5 space-y-1"><template x-for="n in a.result.ai_summary.next_steps"><li x-text="n"></li></template></ul></div>
                </div>
              </div>
            </template>
            <template x-if="a.result && !a.result.ai_summary">
              <div class="panel-b flex flex-wrap items-center gap-3"><span class="text-slate-600">Summary unavailable.</span>
                <button class="btn" @click="regen()" :disabled="!!busy" data-testid="regen-summary">Regenerate summary</button></div>
            </template>
          </div>

          <div x-show="a.result?.ai_summary" class="panel">
            <div class="panel-h"><span>Customer explanation</span>
              <button class="btn h-6 text-[12px] normal-case tracking-normal" data-testid="toggle-explanation" @click="showLocal = !showLocal"
                      x-text="showLocal ? 'Show English' : 'Show local language'"></button></div>
            <div class="panel-b">
              <p class="whitespace-pre-line" x-text="showLocal ? a.result?.ai_summary?.customer_explanation_local : a.result?.ai_summary?.customer_explanation_en"></p>
              <p class="text-[12px] text-slate-500 mt-2">Returned to the client via API for display to its customer.</p>
            </div>
          </div>

          <div x-show="a.result" class="panel" data-testid="review-panel">
            <div class="panel-h"><span>Analyst review</span></div>
            <template x-if="a.review">
              <div data-testid="review-card" class="panel-b space-y-1">
                <div>Final recommendation <span class="label" :class="recClass(a.review.final_recommendation)" x-text="a.review.final_recommendation"></span>
                  <span class="text-slate-500" x-text="'(' + a.review.action + ')'"></span></div>
                <div class="text-[12px] text-slate-500" x-text="'by ' + a.review.analyst_email + ' · ' + dateStr(a.review.at)"></div>
                <p x-show="a.review.note" x-text="a.review.note"></p>
              </div>
            </template>
            <template x-if="!a.review">
              <div class="panel-b space-y-3">
                <div class="flex flex-wrap gap-4">
                  <label class="flex items-center gap-2"><input type="radio" value="accept" x-model="review.action"> Accept recommendation</label>
                  <label class="flex items-center gap-2"><input type="radio" value="override" x-model="review.action" data-testid="review-override"> Override</label>
                </div>
                <select x-show="review.action === 'override'" x-model="review.final_recommendation" class="field">
                  <option value="favorable">favorable</option><option value="review">review</option><option value="unfavorable">unfavorable</option></select>
                <textarea x-model="review.note" placeholder="Note (optional)" class="field w-full h-16 py-1"></textarea>
                <button class="btn btn-primary" :disabled="!!busy" @click="submitReview()" data-testid="review-submit">Submit review</button>
              </div>
            </template>
          </div>

          <div class="panel">
            <div class="panel-h"><span>Audit trail</span></div>
            <div class="overflow-x-auto">
              <table class="tbl">
                <thead><tr><th>Time</th><th>Event</th><th>Actor</th></tr></thead>
                <tbody><template x-for="e in a.events"><tr>
                  <td class="whitespace-nowrap num text-slate-500" x-text="dateStr(e.at)"></td>
                  <td class="font-mono text-[12px]" x-text="e.type"></td>
                  <td class="text-slate-600 break-all" x-text="e.actor"></td></tr></template></tbody>
              </table>
            </div>
          </div>
        </div>
      </template>
    </section>
  </main>
</div>
</body>
</html>
```

In `app/static/demo/login.html`, change the head line
`<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KasFlow demo login</title>`
to
`<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KasFlow demo login</title><link rel="icon" href="/static/img/logo.svg" type="image/svg+xml">`

- [ ] **Step 4: Run the tests and check the syntax**

Run: `.venv/bin/pytest && node --check app/static/js/console.js && node --check app/static/js/icons.js`
Expected: all pass, and node exits 0.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(ui): restyle sign-in and analyst console in the pastel IB-style system

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Collection page

**Files:**
- Replace: `app/static/collect.html`
- Modify: `app/static/js/collect.js` (import the icons and add an `icon` method)

**Interfaces:**
- Consumes: `icon()` and the CSS from Task 1
- Produces: the same hooks as before: `lang`, `file-input`, `take-photo`, `capture`, `close-camera`, `collect-item`, `item-done`, `item-remove`, `done`, `thanks`, `state-invalid`, `state-expired`, `state-completed`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_design.py`:
```python
def test_collect_page_uses_the_design_system(client):
    c = client.get("/c/some-token").text
    assert 'class="tile"' in c and "icon('camera'" in c and 'rel="icon" href="/static/img/logo.svg"' in c
    assert 'from "/static/js/icons.js"' in client.get("/static/js/collect.js").text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_design.py::test_collect_page_uses_the_design_system`
Expected: FAIL.

- [ ] **Step 3: Write the page and update `collect.js`**

`app/static/collect.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>KasFlow · Share records</title>
  <link rel="icon" href="/static/img/logo.svg" type="image/svg+xml">
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="/static/css/app.css">
  <script type="module" src="/static/js/collect.js"></script>
</head>
<body class="kf min-h-screen">
<div x-data="collectApp" x-cloak class="max-w-[480px] mx-auto p-3">
  <div class="panel overflow-hidden">
    <div class="topbar"><div class="flex items-center gap-2 px-3 h-11">
      <img src="/static/img/logo.svg" class="w-6 h-6" alt="">
      <span class="wordmark"><span class="kas">Kas</span><span class="flow">Flow</span></span>
      <select x-model="lang" data-testid="lang" class="field ml-auto text-[12px]">
        <option value="id">Bahasa Indonesia</option><option value="fil">Filipino</option>
        <option value="vi">Tiếng Việt</option><option value="en">English</option></select>
    </div></div>

    <div class="panel-b">
      <p x-show="state === 'loading'" class="py-10 text-center text-slate-400"><span class="spinner"></span></p>
      <p x-show="state === 'invalid'" data-testid="state-invalid" class="py-10 text-center" x-text="t('invalid_link')"></p>
      <p x-show="state === 'expired'" data-testid="state-expired" class="py-10 text-center" x-text="t('expired_link')"></p>
      <p x-show="state === 'completed'" data-testid="state-completed" class="py-10 text-center" x-text="t('already_completed')"></p>
      <div x-show="state === 'thanks'" data-testid="thanks" class="py-10 text-center">
        <div class="mx-auto w-11 h-11 flex items-center justify-center border border-[color:var(--pos-line)] bg-[color:var(--pos-bg)] text-[color:var(--pos-ink)]" x-html="icon('check', 24)"></div>
        <h2 class="text-[16px] font-semibold mt-3" x-text="t('thanks_title')"></h2>
        <p class="text-slate-600 mt-1" x-text="t('thanks_body')"></p>
      </div>

      <div x-show="state === 'ready'">
        <h1 class="text-[16px] font-semibold" x-text="t('title')"></h1>
        <p class="mt-1" x-text="t('requesting')"></p>
        <p class="text-[12px] text-slate-500 mt-2 border-l-[3px] border-[color:var(--info-line)] pl-2" x-text="t('consent_notice')"></p>
        <div class="grid grid-cols-2 gap-2 mt-4">
          <label class="tile">
            <input type="file" multiple accept="application/pdf,image/png,image/jpeg,.csv,text/csv" class="hidden"
                   data-testid="file-input" @change="onFiles($event)">
            <span class="ico text-[color:var(--primary)]" x-html="icon('upload', 24)"></span><span x-text="t('upload')"></span></label>
          <button type="button" class="tile" data-testid="take-photo" @click="takePhoto()">
            <span class="ico text-[color:var(--primary)]" x-html="icon('camera', 24)"></span><span x-text="t('take_photo')"></span></button>
          <input type="file" accept="image/*" capture="environment" class="hidden" x-ref="mobileCam" @change="onMobilePhoto($event)">
        </div>
        <div class="mt-2 border border-dashed border-[color:var(--border)] p-2 text-center text-[12px] text-slate-500"
             @dragover.prevent @drop.prevent="onFiles($event)" x-text="t('drop_hint')"></div>
        <ul class="mt-3 border border-[color:var(--border)] divide-y divide-[color:var(--border)]" x-show="visibleItems.length">
          <template x-for="it in visibleItems" :key="it.id">
            <li data-testid="collect-item" class="flex flex-wrap items-center gap-2 px-2 py-2">
              <span class="ico text-slate-500" x-html="icon('document')"></span>
              <span class="truncate flex-1 min-w-0" x-text="it.label"></span>
              <span x-show="it.status === 'processing'" class="text-[12px] text-slate-500"><span class="spinner"></span> <span x-text="t('processing')"></span></span>
              <span x-show="it.status === 'done'" class="label label-pos" data-testid="item-done"><span class="ico" x-html="icon('check')"></span><span x-text="t('n_read', { n: String(it.txn_count) })"></span></span>
              <span x-show="it.status === 'failed'" class="label label-neg whitespace-normal"><span class="ico" x-html="icon('cross')"></span><span x-text="t('extract_failed')"></span></span>
              <button x-show="it.status === 'failed'" data-testid="item-remove" class="text-[12px] underline" @click="remove(it.id)" x-text="t('remove')"></button>
            </li>
          </template>
        </ul>
        <p x-show="err" class="label label-neg whitespace-normal w-full mt-2" x-text="err"></p>
        <button class="btn btn-primary w-full justify-center h-10 mt-4 text-[14px]"
                :disabled="doneCount === 0 || busy" data-testid="done" @click="done()" x-text="t('done')"></button>
      </div>
    </div>
    <div class="border-t border-[color:var(--border)] bg-[color:var(--strip)] px-3 py-2 text-center text-[11px] text-slate-500" x-text="t('secured_by')"></div>
  </div>

  <div x-show="camOpen" class="fixed inset-0 bg-[#1F2A37]/85 flex flex-col items-center justify-center p-4 z-50">
    <video x-ref="video" autoplay playsinline muted class="max-w-full max-h-[70vh] border border-[color:var(--border)]"></video>
    <div class="flex gap-2 mt-4">
      <button class="btn btn-primary h-9" data-testid="capture" @click="capture()"><span class="ico" x-html="icon('camera')"></span><span x-text="t('capture')"></span></button>
      <button class="btn h-9" data-testid="close-camera" @click="closeCam()"><span class="ico" x-html="icon('cross')"></span><span x-text="t('close')"></span></button>
    </div>
    <p class="text-white text-sm mt-3" x-show="doneCount > 0" x-text="t('n_read', { n: String(items.filter(i => i.status === 'done').reduce((s, i) => s + i.txn_count, 0)) })"></p>
  </div>
</div>
</body>
</html>
```

In `app/static/js/collect.js`:
- After `import { T } from "/static/js/i18n.js";`, add the line `import { icon as svgIcon } from "/static/js/icons.js";`.
- After the line `lang: "en", info: null, state: "loading", items: [], camOpen: false, photoN: 0, busy: false, err: "",`, add the line `  icon(name, size) { return svgIcon(name, size); },`.

- [ ] **Step 4: Run the tests and check the syntax**

Run: `.venv/bin/pytest && node --check app/static/js/collect.js`
Expected: all pass, and node exits 0.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(ui): restyle the collection page with tiles and SVG icons

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: PinjamCepat, intro/outro cards, captions and docs, with the global no-emoji rule

**Files:**
- Modify: `app/static/demo/client.html`, `app/static/js/client-demo.js`, `video/record_demo.ts`, `README.md`
- Replace: `app/static/demo/intro.html`, `app/static/demo/outro.html`

**Interfaces:**
- Consumes: `icon()` from Task 1
- Produces:
  - `client-demo.js` gains an `icon(name, size)` method
  - the caption bar style follows spec §13

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_design.py`:
```python
FLAGS = re.compile("[\U0001F1E6-\U0001F1FF]{2}")
EMOJI = re.compile("[\U0001F000-\U0001FAFF⌀-⏿■-◿☀-➿⬀-⯿️‍]")
DOCS = [ROOT / "README.md", ROOT / "SUBMISSION.md", ROOT / "docs" / "pitch-outline.md", ROOT / "video" / "record_demo.ts"]


def checked_files():
    static = sorted(p for p in STATIC_DIR.rglob("*") if p.suffix in {".html", ".js", ".css", ".svg"})
    return static + DOCS


@pytest.mark.parametrize("path", checked_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_emoji_except_country_flags(path):
    text = FLAGS.sub("", path.read_text(encoding="utf-8"))
    found = sorted(set(EMOJI.findall(text)))
    assert not found, f"emoji in {path.relative_to(ROOT)}: {found}"


@pytest.mark.parametrize("page", sorted(STATIC_DIR.rglob("*.html")), ids=lambda p: p.name)
def test_every_page_links_the_favicon(page):
    assert 'rel="icon" href="/static/img/logo.svg"' in page.read_text(encoding="utf-8")


def test_every_icon_used_exists():
    names = icon_names()
    used = set()
    for p in STATIC_DIR.rglob("*"):
        if p.suffix in {".html", ".js"}:
            text = p.read_text(encoding="utf-8")
            used |= set(re.findall(r"""icon\(\s*['"](\w+)['"]""", text))
            for pair in re.findall(r"""icon\([^)]*\?\s*['"](\w+)['"]\s*:\s*['"](\w+)['"]""", text):
                used |= set(pair)  # ternaries such as icon(ok ? 'check' : 'cross')
    kinds = (STATIC_DIR / "js" / "console.js").read_text(encoding="utf-8").split("const KIND_ICON = {", 1)[1].split("};", 1)[0]
    used |= set(re.findall(r'"(\w+)"', kinds))  # values of { open_finance: "bank", ... }
    assert {"bank", "wallet", "camera", "upload", "plug"} <= used
    assert used <= names, used - names
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_design.py`
Expected: FAIL. The emoji check flags `demo/client.html`, `demo/intro.html`, `demo/outro.html` and `README.md`; the favicon check flags `client.html`, `intro.html` and `outro.html`; `test_every_icon_used_exists` fails because `wallet` isn't used yet.

- [ ] **Step 3: Update PinjamCepat, the cards, the captions and the README**

In `app/static/demo/client.html` make these exact replacements:
1. **Favicon.** `<title>PinjamCepat (demo client)</title>` becomes
   `<title>PinjamCepat (demo client)</title>\n  <link rel="icon" href="/static/img/logo.svg" type="image/svg+xml">`
2. **Header mark.** `<span class="text-2xl">⚡</span>` becomes
   `<svg width="22" height="22" viewBox="0 0 24 24" fill="#fff" aria-hidden="true"><path d="M13 2 4 14h6l-1 8 9-12h-6z"/></svg>`
3. **Received state.** `<div class="text-5xl">✅</div>` becomes
   `<svg class="mx-auto" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8 12.5 3 3 5-6"/></svg>`
4. **Under-review state.** `<div class="text-5xl">⏳</div>` becomes
   `<svg class="mx-auto" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ea580c" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`
5. **Consent account icons.** `<span x-text="acc.type === 'bank' ? '🏦' : '👛'"></span>` becomes
   `<span class="inline-flex align-[-3px] text-orange-600" x-html="icon(acc.type === 'bank' ? 'bank' : 'wallet')"></span>`

In `app/static/js/client-demo.js`:
- After the first `import` line, add `import { icon as svgIcon } from "/static/js/icons.js";`.
- After the line `consentOpen: false, log: [], phase: "form", collectionUrl: "", assessmentId: null, busy: false, err: "",`, add `  icon(name, size) { return svgIcon(name, size); },`.

`app/static/demo/intro.html`:
```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KasFlow</title>
  <link rel="icon" href="/static/img/logo.svg" type="image/svg+xml">
  <script src="https://cdn.tailwindcss.com"></script></head>
<body class="min-h-screen flex items-center justify-center p-10" style="background:#F5F7FA;color:#1F2A37;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif">
  <main class="w-full max-w-5xl bg-white border border-[#D9DEE7]" style="border-top:4px solid #3B6FB6">
    <div class="px-12 pt-10 pb-12">
      <div class="flex items-center gap-3">
        <img src="/static/img/logo.svg" class="w-10 h-10" alt="">
        <span class="text-3xl font-semibold"><span style="color:#1E3A5F">Kas</span><span style="color:#2E8B62">Flow</span></span>
      </div>
      <h1 class="text-5xl font-semibold mt-6 leading-tight" style="color:#1E3A5F">Credit signals from any data</h1>
      <ol class="mt-10 border-y border-[#D9DEE7] divide-y divide-[#D9DEE7] text-2xl">
        <li class="flex gap-6 py-5"><span class="font-semibold tabular-nums" style="color:#3B6FB6">01</span>
          <span>Asia-Pacific MSME credit gap: ~US$2.5 trillion <span class="text-lg" style="color:#667085">(ADB, 2024)</span></span></li>
        <li class="flex gap-6 py-5"><span class="font-semibold tabular-nums" style="color:#3B6FB6">02</span>
          <span>SEA financial data is scattered across banks, e-wallets, QRIS — and paper</span></li>
        <li class="flex gap-6 py-5"><span class="font-semibold tabular-nums" style="color:#3B6FB6">03</span>
          <span>Lending, BNPL, rental &amp; insurance all need the same answer: can this customer afford it?</span></li>
      </ol>
    </div>
  </main>
</body>
</html>
```

`app/static/demo/outro.html`:
```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KasFlow</title>
  <link rel="icon" href="/static/img/logo.svg" type="image/svg+xml">
  <script src="https://cdn.tailwindcss.com"></script></head>
<body class="min-h-screen flex items-center justify-center p-10" style="background:#F5F7FA;color:#1F2A37;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif">
  <main class="w-full max-w-5xl bg-white border border-[#D9DEE7]" style="border-top:4px solid #3B6FB6">
    <div class="px-12 pt-8 pb-10">
      <div class="flex items-center gap-3">
        <img src="/static/img/logo.svg" class="w-9 h-9" alt="">
        <span class="text-2xl font-semibold"><span style="color:#1E3A5F">Kas</span><span style="color:#2E8B62">Flow</span></span>
      </div>
      <h1 class="text-4xl font-semibold mt-4" style="color:#1E3A5F">Embed credit signals in a day</h1>
      <svg viewBox="0 0 900 220" class="w-full mt-6" font-family="system-ui, sans-serif" font-size="15">
        <defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="#98A2B3"/></marker></defs>
        <rect x="10" y="80" width="170" height="60" rx="2" fill="#FDF1DC" stroke="#F2D9A8"/><text x="95" y="115" text-anchor="middle" fill="#8A5A12">Client app / API</text>
        <rect x="250" y="4" width="210" height="54" rx="2" fill="#EEF2F7" stroke="#D9DEE7"/><text x="355" y="36" text-anchor="middle" fill="#344054">Firebase Hosting + Auth</text>
        <rect x="250" y="80" width="210" height="60" rx="2" fill="#E6EEF9" stroke="#C3D5EE"/><text x="355" y="106" text-anchor="middle" fill="#2F5C99" font-weight="600">KasFlow API</text><text x="355" y="127" text-anchor="middle" fill="#2F5C99" font-size="13">Cloud Run</text>
        <rect x="560" y="24" width="200" height="54" rx="2" fill="#E3F4EA" stroke="#B7E0C7"/><text x="660" y="56" text-anchor="middle" fill="#1F6B45">Firestore</text>
        <rect x="560" y="142" width="200" height="54" rx="2" fill="#EEE8F8" stroke="#D5C8EE"/><text x="660" y="174" text-anchor="middle" fill="#5B3F99">Gemini (Vertex AI)</text>
        <g stroke="#98A2B3" stroke-width="1.5" fill="none" marker-end="url(#ar)">
          <line x1="180" y1="110" x2="248" y2="110"/><line x1="355" y1="58" x2="355" y2="78"/>
          <line x1="460" y1="100" x2="558" y2="56"/><line x1="460" y1="122" x2="558" y2="168"/>
        </g>
      </svg>
      <ol class="mt-6 border-y border-[#D9DEE7] divide-y divide-[#D9DEE7] text-xl">
        <li class="flex gap-6 py-3"><span class="font-semibold tabular-nums" style="color:#3B6FB6">01</span><span>Open finance first, any data as fallback — even paper, via camera</span></li>
        <li class="flex gap-6 py-3"><span class="font-semibold tabular-nums" style="color:#3B6FB6">02</span><span>Deterministic, explainable scores; AI reads and explains</span></li>
        <li class="flex gap-6 py-3"><span class="font-semibold tabular-nums" style="color:#3B6FB6">03</span><span>Embed in a day: REST API + hosted collection page</span></li>
      </ol>
      <p class="mt-6 text-sm" style="color:#667085">Built on Gemini · Cloud Run · Firestore · Firebase</p>
    </div>
  </main>
</body>
</html>
```

In `video/record_demo.ts`, replace the caption style block:
```typescript
    Object.assign(d.style, {
      position: "fixed", left: "50%", bottom: "28px", transform: "translateX(-50%)", background: "rgba(0,0,0,0.75)",
      color: "#fff", fontSize: "22px", padding: "10px 18px", borderRadius: "12px", zIndex: "2147483647",
      maxWidth: "90%", textAlign: "center", fontFamily: "system-ui, sans-serif", pointerEvents: "none",
    });
```
with:
```typescript
    Object.assign(d.style, {
      position: "fixed", left: "50%", bottom: "28px", transform: "translateX(-50%)", background: "rgba(30,58,95,0.92)",
      color: "#fff", fontSize: "20px", padding: "10px 18px", borderRadius: "0", borderLeft: "3px solid #3FA37A",
      zIndex: "2147483647", maxWidth: "90%", textAlign: "center", fontFamily: "system-ui, sans-serif", pointerEvents: "none",
    });
```

In `README.md`, change the first line `# 💧 KasFlow — credit signals from any data` to `# KasFlow — credit signals from any data`.

- [ ] **Step 4: Run the tests and check the syntax**

Run: `.venv/bin/pytest && node --check app/static/js/client-demo.js`
Expected: all pass, and node exits 0.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(ui): remove emoji from client demo, cards, captions and docs; enforce no-emoji rule

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Browser page check, then re-record the video

**Files:**
- Create: `video/check_pages.ts`
- Modify: `video/package.json` (add the `check` script)

**Interfaces:**
- Consumes: every page and the stub-mode server
- Produces:
  - `npx tsx check_pages.ts`, which exits 1 on any console or page error or a failed layout assertion, and writes screenshots to `video/out/pages/`
  - a new `video/out/*.webm` recording of 3:00–4:00

- [ ] **Step 1: Write the page check**

`video/check_pages.ts`:
```typescript
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
```

In `video/package.json`, change `"scripts": { "record": "tsx record_demo.ts" },` to `"scripts": { "record": "tsx record_demo.ts", "check": "tsx check_pages.ts" },`.

- [ ] **Step 2: Run the page check against the stub server**

Run:
```bash
SEED_ON_START=true .venv/bin/uvicorn app.main:app --port 8080 &
sleep 3
(cd video && npx tsx check_pages.ts)
kill %1
```
Expected: `pages OK: screenshots in video/out/pages/`.

Open every screenshot in `video/out/pages/` and check it against spec §9.0:
- pastel top bar and logo
- no emoji except flags
- rectangular labels
- score block with its tick marks
- readable tables
- the collection page fits 375 px

If something renders wrong, fix the markup or CSS and re-run. Don't loosen the assertions.

- [ ] **Step 3: Re-record the demo video**

Run:
```bash
rm -f video/out/*.webm
SEED_ON_START=true .venv/bin/uvicorn app.main:app --port 8080 &
sleep 3
(cd video && BASE_URL=http://localhost:8080 DEMO_LOGIN_KEY=dev-login-key npx tsx record_demo.ts)
kill %1
~/Library/Caches/ms-playwright/ffmpeg-1010/ffmpeg-mac -i video/out/*.webm -f null - 2>&1 | grep Duration
```
Expected: `video saved: …webm`, and a duration between `00:03:00` and `00:04:00`. The ffmpeg binary bundled with Playwright is enough to read the duration. If the duration is out of range, re-record with `PACE`.

Then pull frames at 30, 55, 75, 95, 120, 150 and 185 s (`ffmpeg-mac -ss <t> -i <webm> -frames:v 1 f<t>.png`) and check that every scene shows the new look with its caption.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add video/check_pages.ts video/package.json
git commit -m "test(ui): add headless page check (console errors, layout, tamper label) for the redesign

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Self-review notes

**Spec coverage:**

| Spec section | Task |
|---|---|
| §9.0 tokens, components, icons, logo, favicon | 1 |
| §9.0 applied to the sign-in page and console, §9.2 | 2 |
| §9.3 collection page tiles and icons | 3 |
| §9.4 PinjamCepat own brand | 4 |
| §9.5 cards without emoji | 4 |
| §13 caption style | 4 |
| §14 docs without emoji | 4 |
| §11 `test_design.py` | Tasks 1–4 |
| §13 duration 3:00–4:00 | 5 |

**Placeholders:** none.

**Type consistency:**
- `icon(name, size)` has the same signature in `icons.js` and in the Alpine wrappers in Tasks 2, 3 and 4.
- `kindIcon` returns icon names that `KIND_ICON` defines, and the test parses those names.
- `PATHS` is the object the tests parse.
