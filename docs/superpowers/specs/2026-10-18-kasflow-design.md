# KasFlow: Design Spec

- **Date:** 2026-10-18
- **Status:** Implemented.
- **Revisions** (all 2026-10-18):
  - **2:** visual redesign (§9.0).
  - **3:** deployment and cost. Covers the Gemini timeouts (§8), scale-to-zero, cost guardrails and bootstrap (§12), the cost slide and its video scene (§9.5, §13), the README cost section (§14), and which files are kept local-only (§2).
- **Audience:** the coding agent that will implement this, plus the human team

---

## 0. Intent (agreed in brainstorming)

**What KasFlow is.** KasFlow is credit-scoring infrastructure for Southeast Asia, sold as a B2B vendor. Any company (a lending company, BNPL provider, property platform, telco and so on) integrates KasFlow by API to assess its customer.

**How it works.**
1. **Open-finance data is the main source.** KasFlow pulls it first.
2. **Extra data only when needed.** If that data is not enough, KasFlow generates a public, token-protected **collection page**. The client embeds it in its own app (iframe) or sends it as a link.
3. **Any format the customer has.** On the collection page the customer adds bank statements, e-wallet screenshots, CSV exports, or **photos of paper records taken with the camera**.
4. **Scoring and explanation.** Python computes all metrics and the score. Gemini only reads documents, maps unknown formats, and writes explanations.
5. **Analyst review.** Analysts (Google sign-in) review results in a console.

**Who it's for.**
- **Paying customer:** the *client* company.
- **End user:** the client's *customer*. Customers may be individuals or businesses (MSMEs).
- **Terminology:** generic, not lending-specific. Use client, customer, assessment, purpose, analyst. Never use "borrower" or "lender" in code or UI.

**Hackathon context.**
- **Build time:** the first working demo is built in about 1–2 hours, mostly by an AI coding agent.
- **Required technology:** Gemini as the LLM, deployed on Google Cloud Run. The submission must describe how Firebase, Firestore, Cloud Run and Gemini are used.
- **Deliverables:**
  - pitch deck (organiser's template; this spec only provides an outline)
  - a 3–4 minute video showing working functionality, recorded with Playwright
  - a deployed link that must stay up through evaluation
  - a GitHub repo
  - a brief description

**Success criteria.**
1. The deployed URL works end to end for a judge with no help: open the demo client page, then sign in to the console with any Google account.
2. The video runs 3:00–4:00 and shows four things:
   - an API-based assessment
   - the embedded collection page, including a camera capture of a paper ledger
   - multi-source merging with trust tracking
   - the analyst review, plus a tamper-detection case
3. Scores are deterministic and unit-tested. The score never depends on the LLM.
4. The submission text clearly names a real role for each of these: Firebase Auth, Firebase Hosting, Firestore, Cloud Run and Gemini.

**Non-goals (deliberately out of scope).**
- **Integrations:** real open-finance rails (simulated by a mock provider), webhooks, and client self-onboarding or a multi-client admin UI. One seeded demo client is enough, but the data model is multi-client.
- **Auth:** password login and analyst invites or whitelists. Any Google account is an analyst in the demo.
- **Infrastructure:** storing original uploaded files (they are discarded after extraction), rate limiting, and background queues.
- **Localization:** the console is English only. The collection page is localized.

---

## 1. Architecture

```
Customer device ──(iframe in client app or direct link)──┐
Client backend ──(X-API-Key)─────────────────────────────┤
Analyst browser ──(Firebase Auth Google ID token)────────┤
                                                         ▼
                 Firebase Hosting  https://<project>.web.app   (rewrite "**" → Cloud Run)
                                                         ▼
                 Cloud Run service "kasflow"  (one FastAPI container, min-instances=0, scales to zero)
                   ├─ static pages (HTML + Alpine.js + Tailwind CDN, no build step)
                   ├─ /api/v1/*          client API (API key)
                   ├─ /api/console/*     analyst API (Firebase ID token)
                   ├─ /api/collect/*     collection page API (URL token)
                   ├─ /api/demo/*        demo client proxy + demo-login custom token
                   ├─ Firestore (Native mode) via firebase-admin / google-cloud-firestore
                   └─ Gemini on Vertex AI via google-genai SDK (service-account auth)
```

**Where each required Google product is used** (this also feeds `SUBMISSION.md`):

| Product | Role |
|---|---|
| **Firebase Auth** | Analyst Google sign-in. Custom tokens for the demo-login page used by video automation. |
| **Firebase Hosting** | Public URL and CDN front door, rewriting to Cloud Run. |
| **Firestore** | Clients, assessments, normalized transactions, and the audit events trail. |
| **Cloud Run** | The whole backend plus the static UI, in one container. |
| **Gemini** | Three jobs: (1) multimodal extraction of transactions from PDFs, screenshots and camera photos of paper ledgers; (2) schema mapping of unknown CSV and JSON formats; (3) the explained risk summary and a customer-facing explanation in the local language. |

**Tech stack (pin these versions):**
- **Python:** 3.12
- **Python packages:**
  - fastapi, uvicorn[standard], pydantic v2, python-multipart, httpx
  - firebase-admin, google-cloud-firestore, google-genai
  - segno (QR codes, server-side SVG)
  - pypdf (only for PDF page-count validation)
  - reportlab and pillow (asset generation scripts only)
  - pytest
- **Frontend libraries:**
  - Alpine.js 3.14.1
  - Tailwind Play CDN (`https://cdn.tailwindcss.com`)
  - Chart.js 4.4.1 (cdnjs or jsdelivr)
  - Firebase JS SDK 10.12.2 modular (from `https://www.gstatic.com/firebasejs/10.12.2/…`)
- **Video tooling:** Node 20 with `@playwright/test` (Chromium), and ffmpeg/ffprobe for the video.

---

## 2. Repository layout

```
kasflow/
  app/
    main.py                # FastAPI app factory; mounts routers & static; /healthz; /config.js
    config.py              # Settings (pydantic-settings or os.environ)
    auth.py                # require_analyst (Firebase ID token), require_client (X-API-Key)
    models.py              # Pydantic models (section 4)
    repo.py                # Repo protocol + FirestoreRepo + InMemoryRepo
    i18n.py                # country → currency, language; server-side strings (few)
    routers/
      client_api.py        # /api/v1/...
      console_api.py       # /api/console/...
      collect_api.py       # /api/collect/...
      demo.py              # /api/demo/..., /demo-login page support
      pages.py             # serves HTML routes: /, /console, /c/{token}, /demo/*
    services/
      mock_provider.py     # simulated SEA open-finance aggregator
      adapters/
        open_finance.py    # provider JSON → Transaction[]
        standard.py        # validate client-pushed standard-format transactions
        csv_mapper.py      # apply a Gemini-produced column mapping to CSV rows
      gemini.py            # extract_document, map_csv_columns, map_json, summarize; RateLimitedGemini
      ratelimit.py         # per-minute sliding window + daily cap (Firestore counter)
      merge.py             # dedupe + internal-transfer detection
      tamper.py            # running-balance reconciliation
      sufficiency.py
      scoring.py
      tokens.py            # collection token generate/hash; API key hash
      pipeline.py          # orchestration (section 6)
    static/
      index.html           # Google sign-in
      console.html         # analyst SPA (hash routes)
      collect.html         # collection page
      demo/client.html     # PinjamCepat mock client app
      demo/intro.html, demo/cost.html, demo/outro.html, demo/login.html
      js/firebase.js, js/console.js, js/collect.js, js/i18n.js, js/client-demo.js, js/icons.js
      css/app.css          # design tokens + components (§9.0)
      img/logo.svg         # logo, also the favicon
  scripts/
    generate_personas.py   # deterministic data + demo_assets
    seed.py                # [local-only] writes demo client + seeded assessments to Firestore
    check_gemini.py        # [local-only] live extraction check on every demo asset
    smoke.py               # [local-only] deployed-URL smoke test
  data/personas/           # generated JSON (committed)
  demo_assets/             # generated PNG/CSV/PDF/y4m (committed, except y4m if >50MB)
  tests/                   # pytest (section 11)
  video/
    package.json, record_demo.ts, check_pages.ts, stitch.sh
  Dockerfile
  firebase.json, .firebaserc, firestore.rules
  bootstrap.sh, deploy.sh  # [local-only] one-command setup + deploy (§12)
  ACCESS.md                # [local-only] deploy runbook
  .env.example
  README.md, SUBMISSION.md
  docs/pitch-outline.md, docs/voiceover-script.md
  docs/superpowers/specs/2026-10-18-kasflow-design.md   (this file)
```

**[local-only]** files are gitignored. They stay on the developer's machine and aren't published, which keeps the public repo clean. Tests for them skip on a fresh clone.

---

## 3. Configuration (environment variables)

| Var | Example | Notes |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | `kasflow-hack` | |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | Vertex AI location for Gemini. `global` is also acceptable if supported. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Default. Before recording, check whether a newer GA Flash model is available in Vertex. If so, set it here; no code change is needed. |
| `DEMO_CLIENT_API_KEY` | random 32-char | Used by the seed (stored hashed) and by the demo client proxy. |
| `DEMO_LOGIN_KEY` | random 32-char | Guards `/demo-login`. Never displayed in the UI. |
| `PUBLIC_BASE_URL` | `https://kasflow-hack.web.app` | Used to build collection URLs. |
| `FIREBASE_WEB_API_KEY`, `FIREBASE_WEB_AUTH_DOMAIN`, `FIREBASE_WEB_PROJECT_ID`, `FIREBASE_WEB_APP_ID` | | Served to the browser by `GET /config.js` as `window.KASFLOW_CONFIG`. |
| `REPO_BACKEND` | `firestore` \| `memory` | `memory` for local dev and tests. |
| `GEMINI_BACKEND` | `vertex` \| `stub` | `stub` returns fixtures from `data/personas/*_extracted.json` (for tests and offline dev). |

Fixed constants live in `app/config.py`:

| Constant | Value |
|---|---|
| `ANNUAL_RATE` | `0.18` |
| `COVERAGE_TARGET` | `1.5` |
| `MIN_MONTHS` | `6` |
| `MIN_INFLOW_TXNS` | `20` |
| `COLLECTION_TTL_HOURS` | `72` |
| `MAX_ITEMS` | `8` |
| `MAX_FILE_BYTES` | `5 * 1024 * 1024` |
| `GEMINI_TIMEOUT_S` | `25` (CSV/JSON mapping and summaries) |
| `GEMINI_EXTRACT_TIMEOUT_S` | `50` (document extraction and `map_json`; a 62-row statement takes 21–30 s live) |
| `GEMINI_DEADLINE_S` | `55` (total per call including a retry; Firebase Hosting rewrites time out at 60 s) |
| `GEMINI_RPM` (env) | `5` live Gemini calls per minute |
| `GEMINI_DAILY_CAP` (env) | `50` live Gemini calls per UTC day |

Country table (`app/i18n.py`):

| Country | Currency | Language |
|---|---|---|
| ID | IDR | `id` |
| PH | PHP | `fil` |
| VN | VND | `vi` |

---

## 4. Data model

### 4.1 Pydantic models (`app/models.py`)

```python
Direction = Literal["in", "out"]
Channel   = Literal["bank", "ewallet", "qris", "card", "cash", "other"]
TxnKind   = Literal["normal", "returned", "loan_repayment", "internal_transfer"]
Trust     = Literal["verified", "extracted"]
SourceKind = Literal["open_finance", "api_push", "upload", "camera"]
Status    = Literal["created", "needs_more_data", "scored", "reviewed", "error"]
Recommendation = Literal["favorable", "review", "unfavorable"]

class Transaction(BaseModel):
    id: str                      # uuid4 hex
    date: date
    amount: Decimal              # > 0, major currency units
    direction: Direction
    description: str = ""
    channel: Channel = "other"
    counterparty: str | None = None
    balance: Decimal | None = None   # running balance after this row, if printed
    currency: str                # ISO code
    kind: TxnKind = "normal"
    source_id: str
    row_index: int               # position within its source (for tamper flags / display)
    duplicate_of: str | None = None  # set by merge; duplicates are excluded from metrics

class Customer(BaseModel):
    name: str
    type: Literal["individual", "business"]
    occupation_or_business_type: str
    country: Literal["ID", "PH", "VN"]
    years_active: float = Field(ge=0)

class Consent(BaseModel):
    ref: str
    provider: str = "openfinance-sea-sim"
    granted_at: datetime
    expires_at: datetime         # granted_at + 30 days

class TamperFlag(BaseModel):
    row_index: int
    expected_balance: Decimal
    actual_balance: Decimal

class Source(BaseModel):
    id: str
    kind: SourceKind
    label: str                   # e.g. "Bank Merapi ••4821", "DompetKu screenshot", "Buku kas photo 1"
    trust: Trust                 # open_finance/api_push(standard) → verified; upload/camera/api_push(auto) → extracted
    txn_count: int
    months_covered: int
    tamper_flags: list[TamperFlag] = []
    added_at: datetime

class Sufficiency(BaseModel):
    months_covered: int
    inflow_txn_count: int
    sufficient: bool
    reasons: list[str]           # human-readable, e.g. "Only 3 of 6 required months covered"

class CollectionItem(BaseModel):
    id: str
    kind: Literal["upload", "camera"]
    filename: str
    mime_type: str
    status: Literal["done", "failed"]
    txn_count: int = 0
    source_id: str | None = None
    error: str | None = None
    added_at: datetime

class Collection(BaseModel):
    token_hash: str
    created_at: datetime
    expires_at: datetime
    completed_at: datetime | None = None
    items: list[CollectionItem] = []

class Metrics(BaseModel):
    months_covered: int
    avg_monthly_inflow: Decimal
    avg_monthly_outflow: Decimal
    avg_monthly_net: Decimal
    income_cv: float
    net_margin: float
    trend_pct: float
    returned_count: int
    debt_burden: float
    verified_share: float
    top_payer_share: float | None   # None for individuals or when counterparty is unknown for >50% of inflow
    tamper_flag_count: int
    monthly: list[dict]             # [{"month":"2026-04","inflow":..,"outflow":..,"net":..}] (for chart)

class ScoreBreakdown(BaseModel):
    stability: int; margin: int; trend: int; returned: int; debt: int; trust: int
    concentration_penalty: int; tamper_penalty: int

class AiSummary(BaseModel):
    headline: str
    summary: str
    strengths: list[dict]   # {"point": str, "metric": MetricKey}
    risks: list[dict]
    data_notes: list[str]
    next_steps: list[str]
    customer_explanation_local: str
    customer_explanation_en: str

class Result(BaseModel):
    metrics: Metrics
    score: int                      # 0–100
    grade: Literal["A", "B", "C", "D"]
    breakdown: ScoreBreakdown
    recommendation: Recommendation
    limited_data: bool
    max_monthly_commitment: Decimal
    installment: Decimal | None
    coverage_ratio: float | None
    suggested_max_amount: Decimal | None
    ai_summary: AiSummary | None     # None if Gemini failed; console shows "Regenerate summary"
    computed_at: datetime

class Review(BaseModel):
    analyst_email: str
    action: Literal["accept", "override"]
    final_recommendation: Recommendation
    note: str = ""
    at: datetime

class Event(BaseModel):
    at: datetime
    actor: str        # "client:<client_id>", "customer", "analyst:<email>", "system"
    type: str         # created, open_finance_fetched, collection_link_issued, item_added, item_failed,
                      # collection_completed, scored, summary_generated, summary_failed, reviewed, error
    detail: dict = {}

class Assessment(BaseModel):
    id: str
    client_id: str
    external_ref: str | None
    customer: Customer
    purpose: str                    # free label, e.g. "loan", "bnpl", "rental"
    requested_amount: Decimal | None
    tenor_months: int | None
    currency: str
    consent: Consent
    status: Status
    error: str | None = None
    sufficiency: Sufficiency | None
    collection: Collection | None
    sources: list[Source]
    result: Result | None
    review: Review | None
    events: list[Event]
    created_at: datetime
    updated_at: datetime
```

`MetricKey` is one of these field names: `months_covered`, `avg_monthly_inflow`, `avg_monthly_outflow`, `avg_monthly_net`, `income_cv`, `net_margin`, `trend_pct`, `returned_count`, `debt_burden`, `verified_share`, `top_payer_share`, `tamper_flag_count`, `coverage_ratio`.

### 4.2 Firestore collections

| Collection | Doc ID | Content |
|---|---|---|
| `clients` | client id (`pinjamcepat`) | `{name, api_key_hash, created_at}` |
| `assessments` | assessment id | `Assessment` without transactions. `collection.token_hash` is queryable. |
| `assessment_transactions` | assessment id | `{transactions: [Transaction...]}`, max 2,000 rows (about 400 KB, well under the 1 MB doc limit) |

Storage details:
- Serialize `Decimal` as string and dates as ISO strings in Firestore.
- Status filtering and sorting in the console list are done in Python, so no composite indexes are needed.
- `firestore.rules` denies all client SDK access (`allow read, write: if false;`). All access goes through the backend.

### 4.3 Repo interface (`app/repo.py`)

```python
class Repo(Protocol):
    def get_client_by_key_hash(self, h: str) -> dict | None: ...
    def get_client(self, client_id: str) -> dict | None: ...
    def put_client(self, client_id: str, data: dict) -> None: ...
    def create_assessment(self, a: Assessment) -> None: ...
    def get_assessment(self, id: str) -> Assessment | None: ...
    def save_assessment(self, a: Assessment) -> None: ...      # full overwrite, sets updated_at
    def list_assessments(self, client_id: str | None = None) -> list[Assessment]: ...
    def find_by_token_hash(self, h: str) -> Assessment | None: ...
    def get_transactions(self, id: str) -> list[Transaction]: ...
    def put_transactions(self, id: str, txns: list[Transaction]) -> None: ...
```

There are two implementations: `FirestoreRepo` and `InMemoryRepo` (dicts). `REPO_BACKEND` selects one in a FastAPI dependency.

---

## 5. External interfaces

### 5.1 Client API (`X-API-Key` header; key is SHA-256 hashed and compared to `clients.api_key_hash`)

**`POST /api/v1/assessments`** → `201`

Request:
```json
{
  "external_ref": "PC-2026-000123",
  "customer": {"name": "Sari Wulandari", "type": "business",
               "occupation_or_business_type": "Warung (grocery kiosk)", "country": "ID", "years_active": 6},
  "purpose": "loan",
  "requested_amount": 50000000,
  "tenor_months": 12,
  "consent": {"ref": "of-sari-001"}
}
```

Behaviour:
- Creates the assessment and fetches open finance from `mock_provider` using `consent.ref`.
- An unknown ref creates no open-finance source, and sufficiency fails.
- Runs the pipeline (§6). If the data is insufficient, it issues a collection link.

Response:
```json
{
  "id": "…",
  "status": "needs_more_data",
  "sufficiency": {"months_covered": 3, "inflow_txn_count": 12, "sufficient": false, "reasons": ["…"]},
  "collection_url": "https://<host>/c/<token>",
  "collection_expires_at": "…",
  "result": null
}
```
When the data is sufficient, `status` is `scored`, `result` holds the public result (below) and `collection_url` is null.

**`POST /api/v1/assessments/{id}/sources`** → `201`

The client pushes data it already holds.
```json
{"label": "Core banking export", "format": "standard", "transactions": [{"date":"2026-09-01","amount":"150000","direction":"in","description":"…","channel":"bank","balance":null,"counterparty":null,"kind":"normal"}]}
```
or
```json
{"label": "Partner wallet API", "format": "auto", "payload": { "any": "json" }}
```
- `standard`: validated by `adapters/standard.py` and marked `trust=verified`.
- `auto`: Gemini `map_json` (payload truncated to 200 KB) and marked `trust=extracted`.
- Afterwards the pipeline re-runs.
- Returns `{source_id, txn_count, status, result}`.

**`GET /api/v1/assessments/{id}`** → public view:
```json
{ "id","external_ref","status","sufficiency",
  "sources": [{"id","kind","label","trust","txn_count","months_covered","tamper_flag_count"}],
  "result": {"score","grade","recommendation","limited_data","max_monthly_commitment","installment",
             "coverage_ratio","suggested_max_amount","headline","customer_explanation_local","customer_explanation_en"},
  "review": {"final_recommendation","at"} | null,
  "collection_expires_at": null | "…"
}
```

Notes:
- The raw token is never stored, so `GET` cannot return the collection URL; it only reports `collection_expires_at`.
- The URL is returned only by the create call and by the endpoint below.

**`POST /api/v1/assessments/{id}/collection-link`** → `{collection_url, collection_expires_at}`
- Issues a new token and invalidates the old one, because only one `token_hash` is stored.

**Errors:**

| Status | Meaning |
|---|---|
| 401 | Missing or bad key |
| 404 | Assessment not found, or it belongs to another client |
| 422 | Validation error |

All error bodies use `{"error": {"code": "...", "message": "..."}}`.

### 5.2 Console API (`Authorization: Bearer <Firebase ID token>`)

`require_analyst`:
- Calls `firebase_admin.auth.verify_id_token`.
- Accepts **any** valid token whose `firebase.sign_in_provider` is `google.com` or `custom`.
- Returns `{uid, email}`. For custom tokens, `email` comes from the `email` developer claim and defaults to `demo-analyst@kasflow.demo`.
- Demo scope: every analyst sees the single demo client's data, and `list_assessments()` returns everything.

| Method & path | Purpose |
|---|---|
| `GET /api/console/me` | `{email, uid}` |
| `GET /api/console/assessments?status=` | List summaries `{id, customer{name,type,country}, purpose, status, score, grade, recommendation, final_recommendation, updated_at}`, sorted by `updated_at` desc |
| `GET /api/console/assessments/{id}` | Full `Assessment` |
| `GET /api/console/assessments/{id}/transactions` | Transactions, with `source_id`, `kind`, `duplicate_of`, and a `tampered: bool` computed from flags |
| `POST /api/console/assessments/{id}/collection-link` | New link: `{collection_url, collection_expires_at, qr_svg}` (QR from `segno`, SVG string) |
| `POST /api/console/assessments/{id}/score` | "Score now with available data". Forces scoring even if insufficient (`limited_data=true`). |
| `POST /api/console/assessments/{id}/summary` | Regenerates the AI summary only |
| `POST /api/console/assessments/{id}/review` | Body `{action: "accept"\|"override", final_recommendation?: Recommendation, note?: str}`. `override` requires `final_recommendation`. Sets status `reviewed`. |

### 5.3 Collection API (public; `{token}` = raw URL token)

Lookup: `sha256(token)` is looked up with `find_by_token_hash`.

| Condition | Response |
|---|---|
| Not found | 404 `invalid_link` |
| `now > expires_at` | 410 `expired_link` |
| `completed_at` set | 409 `already_completed` (page shows the thank-you state) |

| Method & path | Purpose |
|---|---|
| `GET /api/collect/{token}` | `{client_name, purpose, customer_first_name, country, language, expires_at, max_items, items: [CollectionItem public fields]}` |
| `POST /api/collect/{token}/items` | `multipart/form-data`: `file`, `kind` (`upload`\|`camera`). See behaviour list below. |
| `POST /api/collect/{token}/complete` | Sets `completed_at`, adds event `collection_completed`, runs the pipeline with `force_score=True`. Returns `{status: "received"}`. **Must finish in under 55 s.** |

`POST /api/collect/{token}/items` behaviour:
1. **Validate the file.** Allowed MIME types are `application/pdf`, `image/png`, `image/jpeg` and `text/csv` (CSV is also accepted when the extension is `.csv`). Max size is 5 MB, and an assessment holds at most 8 items.
2. **Extract synchronously.**
   - PDF and images go to `gemini.extract_document`.
   - CSV goes to `gemini.map_csv_columns` and then `csv_mapper.apply`.
3. **Success** (at least 1 transaction extracted):
   - Create a `Source` with `kind = item.kind` and `trust=extracted`, and run `tamper.check` on it.
   - Append the transactions, then run merge and the sufficiency check. **Do not score yet**; scoring happens on `complete`.
   - Return `{item_id, status:"done", txn_count}`.
4. **Failure:** the item is saved with `status:"failed"` and `error` set to a localized message key. Return `200` with `{status:"failed", message_key:"extract_failed"}`.
5. **Rate limits:** when the live Gemini limit is reached, return `429` and don't create an item:
   - `rate_limited` when the per-minute limit is reached;
   - `daily_limit_reached` when the daily cap is reached.
   
   The page shows the localized `busy` or `daily_limit` message (§12, cost guardrails).
6. **Discard the file bytes** once processing finishes.

### 5.4 Demo endpoints

**`POST /api/demo/client/apply`** (public; used only by `/demo/client`)
- Body: `{persona: "sari"|"paolo"|"linh", purpose, requested_amount, tenor_months}`.
- Builds a client API request from the persona's customer profile and consent ref.
- Sends it as a **real HTTP call to the app's own `/api/v1/assessments`**, using `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` with `DEMO_CLIENT_API_KEY`.
- Returns `{request: {...the exact JSON sent...}, response: {...the exact JSON received...}}` for the API log panel.

**`GET /api/demo/assessment/{id}`** (public)
- Proxies `GET /api/v1/assessments/{id}` the same way, so the demo client page can poll status.

**`GET /api/demo/custom-token?key=`**
- Returns 403 unless `key == DEMO_LOGIN_KEY`.
- Otherwise calls `firebase_admin.auth.create_custom_token("demo-analyst", {"email": "demo-analyst@kasflow.demo"})` and returns `{token}`.
- Requires the Cloud Run service account to have `roles/iam.serviceAccountTokenCreator` on itself.

### 5.5 Pages (`routers/pages.py`)

| Route | File | Notes |
|---|---|---|
| `/` | `index.html` | "Sign in with Google" (`signInWithPopup`), then redirect to `/console`. If already signed in, go straight to `/console`. |
| `/console` | `console.html` | Requires a Firebase user, otherwise redirects to `/`. |
| `/c/{token}` | `collect.html` | Response header `Content-Security-Policy: frame-ancestors *`, and **no** `X-Frame-Options`. |
| `/demo/client` | `demo/client.html` | |
| `/demo/intro`, `/demo/outro` | static cards | |
| `/demo-login` | `demo/login.html` | Reads `?key=`, gets a custom token, calls `signInWithCustomToken`, then redirects to `/console`. |
| `/docs` | FastAPI Swagger | Title "KasFlow Client API". Document only the `/api/v1` routes; other routers use `include_in_schema=False`. |
| `/config.js` | | `window.KASFLOW_CONFIG = {firebase:{apiKey,authDomain,projectId,appId}}` |
| `/healthz` | | `{ok:true}` |

---

## 6. Pipeline (`services/pipeline.py`)

```python
def run(assessment_id, *, force_score: bool = False) -> Assessment:
    a = repo.get_assessment(id); txns = repo.get_transactions(id)
    txns = merge.apply(txns, sources=a.sources)            # §6.3
    a.sufficiency = sufficiency.evaluate(txns)             # §6.4
    if not a.sufficiency.sufficient and not force_score:
        if a.collection is None or expired: issue collection link (§6.5)
        a.status = "needs_more_data"
    else:
        a.result = scoring.score(txns, a)                  # §7 (pure)
        a.result.limited_data = not a.sufficiency.sufficient
        a.result.ai_summary = gemini.summarize(a, a.result) # §8.3; on failure → None + event summary_failed
        a.status = "scored"   # unless already "reviewed" — re-scoring after review resets status to "scored" and clears review
    persist; append events; return a
```

`create_assessment` runs these steps:
1. Build the `Assessment` (currency from the country table, consent `granted_at=now`, `expires_at=now+30d`).
2. Fetch the open-finance data with `mock_provider.fetch(ref)`.
3. Convert it with `adapters.open_finance.to_transactions`, producing one `Source` per account (`kind=open_finance`, `trust=verified`).
4. Run `tamper.check` on each source.
5. Save the transactions, then call `run(id)`.

On any unexpected exception inside the pipeline:
- set `status="error"` and `error=str(e)[:300]`, and add an `error` event
- re-raise as HTTP 500 with a generic body

### 6.1 Mock open-finance provider (`services/mock_provider.py`)

- Loads `data/personas/{persona}_open_finance.json`, using the mapping `of-sari-001`→sari, `of-paolo-001`→paolo, `of-linh-001`→linh.
- An unknown ref returns `{"accounts": []}`.

Provider format (intentionally different from ours, so the adapter has real work to do):
```json
{"provider":"openfinance-sea-sim","consent_ref":"of-sari-001","fetched_at":"…",
 "accounts":[{"account_id":"acc_1","institution":"Bank Merapi","type":"bank","currency":"IDR","masked_number":"••4821",
   "transactions":[{"txn_id":"t1","posted":"03/07/2026","amt":"1250000.00","cr_dr":"CR","narrative":"TRF DARI UD MAKMUR",
                    "category":"SALES","running_bal":"8450000.00","counterparty_name":"UD Makmur"}]}]}
```

`adapters/open_finance.py` mapping:

| Provider field | Our field |
|---|---|
| `posted` | `date` (parsed `%d/%m/%Y`) |
| `amt` | `amount` (Decimal) |
| `cr_dr` | `direction`: `CR`→in, `DR`→out |
| `narrative` | `description` |
| account `type` | `channel`: `bank`→bank, `ewallet`→ewallet, `qris`→qris |
| `category` | `kind`: `LOAN`→loan_repayment, `RETURNED`→returned, anything else→normal |
| `running_bal` | `balance` |
| `counterparty_name` | `counterparty` |

The source label is `"{institution} {masked_number}"`.

### 6.2 Source trust

| Source | Trust |
|---|---|
| `open_finance` | `verified` |
| `api_push` with `format=standard` | `verified` |
| `api_push` with `format=auto`, `upload`, `camera` | `extracted` |

### 6.3 Merge (`services/merge.py`, pure)

**Input:** all transactions plus their sources. **Output:** the same list with `duplicate_of` and `kind` updated. The function is idempotent: it resets `duplicate_of=None` and changes `internal_transfer` back to `normal` before recomputing.

1. **Duplicates.**
   - Group by `(date, amount, direction)` across **different** `source_id`s.
   - Within a group, keep the transaction from the most trusted source (`verified` > `extracted`; ties go to the earliest `added_at` source).
   - Mark the others `duplicate_of = kept.id`.
   - Duplicates are excluded from all metrics and counts.
2. **Internal transfers.**
   - For each non-duplicate `out` transaction on channel `bank`, look for a non-duplicate `in` transaction on channel `ewallet` with the same amount, dated the same day or the next day.
   - If found, mark **both** `kind="internal_transfer"`. Each transaction can be paired at most once.
   - Internal transfers are excluded from inflow, outflow and counts.

### 6.4 Sufficiency (`services/sufficiency.py`, pure)

- **Effective transactions:** not duplicates and not `internal_transfer`.
- `months_covered`: the number of distinct `YYYY-MM` values among effective transactions.
- `inflow_txn_count`: the count of effective transactions with `direction=in`.
- `sufficient = months_covered >= 6 and inflow_txn_count >= 20`.
- `reasons` lists each failing condition in English, e.g. `"Only 3 of 6 required months covered"` or `"Only 12 of 20 required incoming transactions"`.

### 6.5 Tokens (`services/tokens.py`)

- `new_collection_token() -> (raw, hash)`: `raw = secrets.token_urlsafe(32)` and `hash = sha256(raw).hexdigest()`.
- The collection URL is `f"{PUBLIC_BASE_URL}/c/{raw}"`, and `expires_at = now + 72h`.
- Issuing a new link replaces `assessment.collection`; existing items are carried over and `completed_at` is reset to `None`.
- `hash_api_key(key) = sha256(key).hexdigest()`.

### 6.6 Tamper check (`services/tamper.py`, pure)

Runs per source, over that source's transactions in `row_index` order.

```
for consecutive rows prev, cur where both have balance:
    expected = prev.balance + cur.amount if cur.direction=="in" else prev.balance - cur.amount
    if abs(expected - cur.balance) > 1: flag(row_index=cur.row_index, expected, actual=cur.balance)
```

- Rows without a balance break the chain: the next row with a balance becomes the new "prev".
- Flags are stored on `Source.tamper_flags`.
- `metrics.tamper_flag_count` is the sum over all sources.

---

## 7. Scoring (`services/scoring.py`, pure, fully unit-tested)

**Effective transactions** are those that are not duplicates and not `internal_transfer`.

**Window:** the last 6 calendar months that contain data, ending at the month of the latest effective transaction. Only include months that have data; there is no zero-filling. Let `M` be the number of months in the window.

**Monthly series:** for each month in the window, `inflow` and `outflow` are the sums of amounts for `in` and `out` transactions, and `net = inflow - outflow`.

### 7.1 Metrics

| Metric | Formula |
|---|---|
| `avg_monthly_inflow` | mean of monthly inflow (likewise for outflow and net) |
| `income_cv` | population stdev(monthly inflow) / mean(monthly inflow). If the mean is 0, use `9.99`. If `M == 1`, use `0.0`. |
| `net_margin` | sum(net) / sum(inflow). `0` if inflow is 0. |
| `trend_pct` | If `M >= 6`: mean(inflow of last 3 months) / mean(inflow of previous 3 months) − 1. If `2 <= M < 6`: compare the last `floor(M/2)` months with the first `floor(M/2)`. If `M < 2`: `0`. Use `0` when the denominator is 0. |
| `returned_count` | Count of effective transactions with `kind=="returned"`, **or** whose description matches the case-insensitive regex `\b(bounce|bounced|returned|reversal|reversed|ditolak|dikembalikan|gagal|ibinalik|hoàn trả|trả lại)\b`. Each transaction counts once. |
| `debt_burden` | sum(out amounts with `kind=="loan_repayment"` **or** description matching `\b(loan|cicilan|angsuran|installment|hulog|trả góp|khoản vay)\b`) / sum(inflow). `0` if inflow is 0. |
| `verified_share` | effective transactions from `verified` sources / all effective transactions |
| `top_payer_share` | Only for `customer.type=="business"`. Over `in` transactions with a counterparty: group by `counterparty.strip().lower()`, then take the largest group's sum / total inflow. `None` if inflow with a counterparty is less than 50% of total inflow, or for individuals. |
| `tamper_flag_count` | Sum of tamper flags across all sources |

### 7.2 Points

| Component | Bands |
|---|---|
| **stability** (25) | cv ≤ 0.20 → 25; ≤ 0.40 → 15; ≤ 0.60 → 8; else 0 |
| **margin** (25) | net_margin ≥ 0.25 → 25; ≥ 0.15 → 18; ≥ 0.05 → 10; > 0 → 5; else 0 |
| **trend** (15) | trend_pct ≥ 0.05 → 15; ≥ −0.05 → 10; ≥ −0.20 → 4; else 0 |
| **returned** (15) | 0 → 15; 1 → 10; 2–3 → 4; else 0 |
| **debt** (10) | debt_burden ≤ 0.10 → 10; ≤ 0.30 → 5; else 0 |
| **trust** (10) | verified_share ≥ 0.70 → 10; ≥ 0.40 → 6; else 3 |
| **concentration_penalty** | −5 if top_payer_share is not None and > 0.50, else 0 |
| **tamper_penalty** | −15 if tamper_flag_count > 0, else 0 |

`score = clamp(sum of all of the above, 0, 100)`.
`grade`: A if ≥ 80, B if ≥ 65, C if ≥ 50, D otherwise.

### 7.3 Recommendation and affordability

1. **Base recommendation:** A or B → `favorable`, C → `review`, D → `unfavorable`.
2. If `tamper_flag_count > 0` and the base is `favorable`, set it to `review`.
3. If `limited_data` and the base is `favorable`, set it to `review`. The caller sets `limited_data`; `score()` takes it as a parameter.
4. `max_monthly_commitment = max(0, avg_monthly_net) / 1.5`.
5. If both `requested_amount` and `tenor_months` are present:
   - `r = 0.18/12`, `n = tenor_months`
   - `installment = P·r / (1 − (1+r)^−n)`
   - `coverage_ratio = avg_monthly_net / installment`
   - If `coverage_ratio < 1.5`:
     - `suggested_max_amount = max_monthly_commitment · (1 − (1+r)^−n) / r`
     - if the recommendation is `favorable`, set it to `review`
   - Otherwise `suggested_max_amount = None`.

Round money values to 2 decimal places, using Decimal throughout.

Signature: `score(txns, *, customer, sources, requested_amount, tenor_months, limited_data) -> Result` (with `ai_summary=None`).

---

## 8. Gemini (`services/gemini.py`)

Client setup:
- `genai.Client(vertexai=True, project=GOOGLE_CLOUD_PROJECT, location=GOOGLE_CLOUD_LOCATION)`.
- Every call uses `types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json", response_schema=<pydantic model>, thinking_config=ThinkingConfig(thinking_budget=0), http_options=HttpOptions(timeout=...))`.
- **Thinking is off for every call.** This was measured live: extraction stayed exact (18/18 cash-book rows, 14/14 e-wallet rows), and long statements finished about 7 s faster.
- **Per-call timeout:**
  - `GEMINI_EXTRACT_TIMEOUT_S` (50 s) for `extract_document` and `map_json`, which produce large outputs;
  - `GEMINI_TIMEOUT_S` (25 s) for everything else.
- **Retry** once after 2 s on any exception, but only if a second full attempt still fits inside `GEMINI_DEADLINE_S` (55 s).
- **Live calls are rate-limited** by `RateLimitedGemini` (§12). Over the limit, it raises `GeminiRateLimited` or `GeminiDailyLimit`, which are subclasses of `GeminiError`.
- Parse with `Model.model_validate_json`.
- On a second failure, raise `GeminiError`.

`GEMINI_BACKEND=stub` returns fixtures:
- **Extraction:** chosen by filename. The fixture is `data/personas/extracted/<asset filename>.json`.
- **Summary:** a deterministic template built from the metrics.

### 8.1 `extract_document(data: bytes, mime_type: str, *, country: str, reference_date: date) -> list[Transaction]`

Response schema:
```python
class ExtractedRow(BaseModel):
    date: str            # YYYY-MM-DD
    description: str
    amount: float        # positive
    direction: Literal["in","out"]
    balance: float | None
    counterparty: str | None
    kind: Literal["normal","returned","loan_repayment"]
class Extraction(BaseModel):
    document_type: Literal["bank_statement","ewallet_history","qris_report","cash_ledger","receipt","other"]
    channel: Literal["bank","ewallet","qris","card","cash","other"]
    institution: str | None
    currency: str | None
    rows: list[ExtractedRow]
```

Prompt (pass the file as `types.Part.from_bytes(data=..., mime_type=...)`, followed by this text):
```
You are a financial document parser working for a credit-assessment service in Southeast Asia.
The attached file was provided by a customer in {country_name}. It may be a bank statement, an
e-wallet transaction history screenshot, a QRIS merchant settlement report, a receipt, or a
photo of a handwritten cash ledger (e.g. Indonesian "buku kas", Filipino "kuwaderno", Vietnamese "sổ thu chi").

Extract EVERY individual monetary transaction row. Rules:
- date: ISO YYYY-MM-DD. If the year is missing, assume the most recent year such that the date is not after {reference_date}.
- amount: positive number in major currency units. Indonesian/Vietnamese formats use "." for thousands and "," for decimals
  (e.g. "1.250.000" = 1250000). Philippine format uses "," for thousands. "Rp", "₱", "đ", "VND", "k" (= ×1000) may appear.
- direction: "in" for money received (credit, CR, masuk, pemasukan, terima, natanggap, thu, +), otherwise "out".
- balance: only if a running-balance column is printed for that row; never compute it yourself.
- kind: "returned" for bounced/reversed/returned items; "loan_repayment" for loan instalments
  (cicilan, angsuran, hulog, trả góp, loan); otherwise "normal".
- counterparty: the other party's name if shown, else null.
- Skip opening/closing balances, totals and subtotals. Never invent rows. If a value is illegible, skip that row.
- For handwritten ledgers, a row with an amount in the income/masuk column is "in"; expense/keluar column is "out".
Return JSON matching the schema.
```

Post-processing in Python:
- Drop rows that have an invalid date, `amount <= 0`, or a date more than 24 months before `reference_date` or after it.
- Assign `currency` (the extraction's value, or the assessment currency), `channel` (from the extraction), `row_index` (the order in which rows came back) and `source_id`.

### 8.2 `map_csv_columns(header: list[str], sample_rows: list[list[str]], *, country) -> CsvMapping` and `map_json(payload, *, country) -> list[Transaction]`

CSV handling:
- Python sniffs the delimiter with `csv.Sniffer`, falling back to `,` and then `;`.
- Python reads the header and the first 10 rows, and sends them to Gemini as text.

`CsvMapping` schema:
```python
class CsvMapping(BaseModel):
    date_column: str
    date_format: str                  # strftime format, e.g. "%d-%m-%Y"
    amount_column: str | None         # single signed or unsigned amount column
    debit_column: str | None          # OR separate debit/credit columns
    credit_column: str | None
    direction_column: str | None
    direction_in_values: list[str]    # values in direction_column meaning money in
    description_column: str | None
    balance_column: str | None
    counterparty_column: str | None
    thousands_separator: Literal[".", ",", " ", ""]
    decimal_separator: Literal[".", ","]
    channel: Literal["bank","ewallet","qris","card","cash","other"]
    status_column: str | None         # if present, keep only rows whose status is in success_values
    success_values: list[str]
```

The prompt is short: "Map this CSV export's columns to the target fields; amounts follow the rules … ; return the mapping only."

`csv_mapper.apply(rows, mapping)` is deterministic Python:
- Parse amounts by removing the thousands separator and replacing the decimal separator with `.`.
- If there is a single amount column with negative values, a negative value means `out`.
- If there are debit and credit columns, whichever is non-empty decides the direction.
- If there is a direction column, compare its value against `direction_in_values`.
- Unit-test this with the QRIS demo CSV and the stored mapping fixture.

`map_json`:
- Sends the JSON payload, truncated to 200 KB, together with the same rules as §8.1.
- Returns the `Extraction` schema.

### 8.3 `summarize(a: Assessment, result: Result) -> AiSummary`

Input: a JSON string containing:
- `customer` (type, occupation_or_business_type, country, years_active; **the name is omitted**)
- `purpose`, `requested_amount`, `tenor_months`, `currency`
- `metrics`, `score`, `grade`, `breakdown`, `recommendation`, `limited_data`
- the affordability fields
- `sources` (label, kind, trust, txn_count, months_covered, tamper_flag_count)
- `sufficiency.reasons`

Prompt:
```
You are a credit analyst assistant. Write an assessment summary for a {purpose} decision using ONLY the data below.
Rules:
- Do not state any number that is not present in the input; do not recompute or change the score or recommendation.
- Every strength and risk must cite exactly one metric key from: {metric_keys}.
- 2–4 strengths, 2–4 risks, 1–3 data_notes (mention source trust, uploads vs verified data, tamper flags if any),
  2–3 next_steps for the analyst.
- Neutral, factual tone. Never reference gender, religion, ethnicity, age, or any protected attribute.
- customer_explanation_local: in {language_name}, 80–120 words, friendly plain language addressed to the customer:
  what their financial data shows and exactly 3 practical tips to strengthen their profile. Do NOT state the score,
  grade, or a final decision (the client company makes the decision).
- customer_explanation_en: the same text in English.
- headline ≤ 120 characters.
DATA:
{json}
```

Validation:
- Any strength or risk whose `metric` is not one of the metric keys is dropped.
- If no strengths or no risks remain after that, treat the call as a failure.

---

## 9. Frontend

### 9.0 Visual system (revision 2)

**Why.** The first version looked AI-generated (emoji, rounded cards, bright pills). KasFlow handles sensitive financial data, so it should look like a serious trading or banking tool. The reference is the Interactive Brokers style: simple, dense and a bit rigid. It uses a **pastel** palette so it stays easy on the eye.

**Rules**
- **No emoji anywhere** in the UI, the intro and outro cards, video captions, README, SUBMISSION.md or the pitch outline. **Exception:** country flag emoji (🇮🇩 🇵🇭 🇻🇳) are allowed to show a customer's country.
- **Icons** are inline SVGs from one module, `app/static/js/icons.js`. Each is 16 px with a 1.5 stroke and `currentColor`. The set: `bank`, `wallet`, `document`, `camera`, `plug`, `upload`, `warning`, `check`, `cross`, `chevron`, `signout`, `clock`, `refresh`. Alpine pages render them with `x-html` from these fixed strings only, never from user or model data.
- **Tailwind stays** (Play CDN). Design tokens and component classes live in `app/static/css/app.css`. No new frontend dependency.

**Palette (pastel)**

| Token | Value | Use |
|---|---|---|
| `--bg` | `#F5F7FA` | page background |
| `--panel` | `#FFFFFF` | panels |
| `--border` | `#D9DEE7` | 1 px borders, table rules |
| `--strip` | `#EEF2F7` | panel header strips, table headers |
| `--topbar` | `#E3ECF8` | top bar, with a 2 px `--primary` line under it |
| `--ink` / `--muted` | `#1F2A37` / `#667085` | text |
| `--primary` | `#3B6FB6` (hover `#2F5C99`) | primary buttons, links, active tab |
| `--pos-bg/-ink/-line` | `#E3F4EA` / `#1F6B45` / `#B7E0C7` | inflow, favorable, verified, done |
| `--neg-bg/-ink/-line` | `#FBE7E6` / `#A23B32` / `#F2C2BE` | outflow, unfavorable, tamper, failed |
| `--warn-bg/-ink/-line` | `#FDF1DC` / `#8A5A12` / `#F2D9A8` | review, needs more data, AI-extracted |
| `--info-bg/-ink/-line` | `#E6EEF9` / `#2F5C99` / `#C3D5EE` | scored, neutral labels |
| chart | inflow `#8CCFA8`, outflow `#F2A7A0`, net line `#3B6FB6` | Chart.js |

**Components**
- **Shape and type:** corner radius 2 px, no shadows, no gradients. System UI font at a 13 px base. Numbers use `font-variant-numeric: tabular-nums` and are right-aligned in tables.
- **Top bar:** logo and wordmark, tab-style navigation (Assessments, API docs), and the analyst email with a sign-out icon.
- **Panels** (`.panel`): white, with a 1 px border and a header strip holding a small, uppercase, letter-spaced title.
- **Tables:** compact rows (about 28 px), zebra striping in `--strip` at 50%, and a sticky header inside scroll areas.
- **Buttons** (`.btn`, `.btn-primary`): rectangular, 28–32 px tall.
- **Labels** (`.label`, with `.label-pos` / `-neg` / `-warn` / `-info` / `-muted`): small rectangles with the pastel background and a 3 px coloured left border. They replace all pills, chips and badges. A metric chip becomes `.label-info`, rendered as a button.
- **Score block:** replaces the ring dial. It shows the large score number, the grade, the recommendation label, and a thin 0–100 bar with tick marks at 50, 65 and 80 (the grade cut-offs). The breakdown is a compact table with a thin bar per component and penalties in `--neg-ink`.

**Logo** (`app/static/img/logo.svg`, also used as the favicon)
- **Mark:** a 24×24 rounded-2 tile in `--topbar` holding three ascending bars in blue `#4A7FC1` (data, ledger), with a green `#3FA37A` polyline across their tops ending in a small arrowhead (cash flow, growth).
- **Wordmark:** "Kas" in `#1E3A5F` and "Flow" in `#2E8B62`, semibold.
- **Tagline:** "Credit signals from any data", in `--muted`.
- `<link rel="icon" href="/static/img/logo.svg" type="image/svg+xml">` goes on every page.

### 9.1 `js/firebase.js`
- Loads the config from `/config.js`.
- Exports `signInGoogle()`, `signInCustom(token)`, `signOut()`, `onUser(cb)`, `getIdToken()`, and `api(path, opts)`. `api()` is a fetch wrapper that adds `Authorization: Bearer`. On a 401 it redirects to `/`.

### 9.2 Console (`console.html` + `js/console.js`, Alpine, hash routing)

**`#list`**
- Header with the analyst email and a sign-out button.
- Status filter tabs (segmented, rectangular): All, Needs more data, Scored, Reviewed, Error.
- Table columns: customer name, type (individual or business, its own column in the rigid table layout), country flag, purpose, status chip, score/grade, recommendation (final recommendation if reviewed), updated time (relative).
- Clicking a row opens `#a/{id}`.
- **No background polling.** A **Refresh** button in the top bar (`data-testid="refresh"`) reloads the current view. No `setInterval` anywhere in the frontend, so a forgotten tab never keeps Cloud Run awake.

**`#a/{id}`**, top to bottom:
1. **Header.** Customer name, type badge, country, occupation or business type, years active, purpose, requested amount and tenor, consent ref and provider with its expiry, and a status chip.
2. **Data sufficiency bar.** "Months covered x/6 · incoming transactions y/20", with the reasons listed.
3. **Collection card.** Shown when the status is `needs_more_data`. A "Generate link" button calls the POST endpoint. Once generated, the card shows:
   - the URL with a Copy button
   - the expiry time
   - the QR code (SVG)
   - the uploaded items and their statuses
   - a "Score now with available data" button
4. **Sources panel.** One card per source showing a kind icon (SVG: `bank` open_finance, `plug` api_push, `document` upload, `camera` camera), the label, a trust label (`.label-pos` "Verified" or `.label-warn` "Extracted by AI"), the transaction count, months covered, and a `.label-neg` "n balance mismatches" label with the `warning` icon if tamper flags exist. The tamper label is rendered only when flags exist (`x-if`, not `x-show`). Expanding a card shows the source's transaction table, with tampered rows highlighted red (expected vs actual) and duplicate or internal-transfer rows greyed out with a label.
5. **Result.**
   - The score block (§9.0) with the grade letter.
   - A recommendation label: `.label-pos` favorable, `.label-warn` review, `.label-neg` unfavorable. Labels for "Limited data" and "Tamper flags".
   - A breakdown bar for each component.
   - Metric cards: average monthly inflow, outflow and net (formatted in the assessment currency using `Intl.NumberFormat` with the locale for the country), income volatility, net margin, trend, returned payments, debt burden, verified share, top-payer share, and affordability (max monthly commitment; installment and coverage ratio; suggested maximum amount).
   - A Chart.js chart: monthly inflow and outflow bars plus a net line.
6. **AI summary panel**, labelled "Drafted by Gemini. The analyst reviews before acting.":
   - headline and summary
   - strengths and risks, each with a metric chip; clicking a chip scrolls to and highlights that metric card
   - data notes and next steps
   - if `ai_summary` is null: "Summary unavailable" with a **Regenerate summary** button
7. **Customer explanation**, with a toggle between the local language and English.
8. **Review panel.** Accept, or Override with a recommendation dropdown, plus a note field and a Submit button. Once reviewed, it shows a read-only review card.
9. **Events timeline.** Shown oldest first, with actor, type and time.

### 9.3 Collection page (`collect.html` + `js/collect.js`)

**Language and access.**
- **Language:** taken from the `language` field in the API response, with a switcher for id, fil, vi and en.
- **Strings:** all in `js/i18n.js` (see the table below).
- **Error states:** invalid link, expired link, and already completed.

**Layout**, mobile-first, maximum width 480 px:
- **Top:** "{client_name} is requesting additional financial information for: {purpose}", then the consent notice ("Your files are read by AI to extract transactions and are not stored."), and a "Secured by KasFlow" footer.
- **Two large tiles** (bordered, square-cornered, with the `upload` and `camera` icons):
  - **Upload files:** `<input type=file multiple accept="application/pdf,image/png,image/jpeg,.csv,text/csv">` plus a drag-and-drop zone. Each file is uploaded sequentially.
  - **Take photo:**
    - On touch devices (`matchMedia('(pointer:coarse)')`), use `<input type=file accept="image/*" capture="environment">`.
    - Otherwise open a modal with a `<video autoplay playsinline>` from `getUserMedia({video:{facingMode:"environment"}})`, plus **Capture** and **Close** buttons.
    - **Capture** draws the frame to a `<canvas>`, calls `toBlob('image/jpeg', 0.92)`, and uploads it with `kind=camera` and filename `photo-<n>.jpg`. The modal stays open so the customer can capture several pages.
    - If camera permission is denied, show a message suggesting Upload instead.
- **Item list:** filename or "Photo n", a spinner, then a `check` icon with "{n} transactions read" or a `cross` icon with "Couldn't read this file — try a clearer photo" with a Remove option. Remove is client-side only: the item stays in the record but has no source. **Keep it simple: no server delete.**
- **Done button:** enabled once at least one item is done.
  - It POSTs `/complete` and shows a thank-you screen.
  - Then, if `window.parent !== window`, it calls `parent.postMessage({type:"kasflow:completed", assessmentId}, "*")`. The assessment ID is included in the GET response.

`js/i18n.js` must contain these keys:

| Group | Keys |
|---|---|
| Request intro and consent | `title`, `requesting`, `consent_notice` |
| Upload and camera controls | `upload`, `take_photo`, `capture`, `close` |
| Item states | `processing`, `n_read`, `extract_failed` |
| Finishing | `done`, `thanks_title`, `thanks_body` |
| Link errors and camera | `invalid_link`, `expired_link`, `already_completed`, `camera_denied`, `secured_by` |
| Rate limits (rev 3) | `busy` (per-minute limit), `daily_limit` (daily cap) |

Each key needs a translation in en, id, fil and vi.

### 9.4 Demo client page (`demo/client.html`): "PinjamCepat" (fictional Indonesian lending app)

**Layout.** Two columns, stacked on mobile:
- **Left:** the client app mock, with its own orange consumer-app branding, clearly a different product from KasFlow. It does **not** use the §9.0 system, but it follows the no-emoji rule: an SVG lightning-bolt mark next to "PinjamCepat", and SVG `bank` / `wallet` icons in the consent modal.
- **Right:** the "API log" panel, dark, monospace, with pretty-printed JSON.
- **Banner:** "Demo client app — simulates a company integrating KasFlow".

**Flow:**
1. **Form.** A persona select, defaulting to "Bu Sari — Warung, Indonesia (thin open-finance data)". The other options are "Paolo — Ride-hailing driver, Philippines (full data)" and "Linh — Online shop, Vietnam (thin data)". The form also has purpose (default `loan`), amount and tenor, prefilled per persona.
2. **"Connect your accounts" button.** Opens a modal styled as a consent screen from the "OpenFinance SEA (simulated)" provider. It lists the persona's accounts and the data scope ("6 months of transactions, valid 30 days"), with Allow and Cancel buttons.
3. **Allow.** Calls `POST /api/demo/client/apply`, and the API log shows the request and response.
4. **Response handling:**
   - **`needs_more_data`:** shows "We need a bit more information" with an `<iframe id="kasflow-frame" src="{collection_url}" allow="camera" style="width:100%;height:720px">`.
   - **`scored`:** shows "Thanks! Your application is under review."
5. **When the iframe finishes.** The page listens for the `kasflow:completed` message, then:
   - hides the iframe and shows "Data received — under review"
   - polls `GET /api/demo/assessment/{id}` every 3 s, appending each response to the API log until the status is `scored`

### 9.5 Intro and outro cards (`/demo/intro`, `/demo/outro`)

Full-screen 1280×720 slides, made of static HTML. They use a pastel navy-on-light layout with the KasFlow logo, and **no emoji**: points are numbered (01, 02, 03) or carry a thin SVG icon.

**Intro slide:**
- Title: "KasFlow: credit signals from any data".
- Three stat lines:
  - "Asia-Pacific MSME credit gap: ~US$2.5 trillion (ADB, 2024)"
  - "SEA financial data is scattered across banks, e-wallets, QRIS — and paper"
  - "Lending, BNPL, rental & insurance all need the same answer: can this customer afford it?"

**Cost slide** (`/demo/cost`):
- A table of measured cost per assessment for each persona: Gemini calls, tokens in and out, and cost ($0.002 / $0.009 / $0.017).
- An infrastructure row: under $0.001.
- A headline: "1–2 US cents per customer".
- The pricing basis: Gemini 2.5 Flash on Vertex AI at $0.30 / $2.50 per 1M tokens.

**Outro slide:**
- An architecture diagram (inline SVG boxes): Client app → KasFlow API (Cloud Run) → Firestore / Gemini, plus Firebase Hosting and Auth.
- Three bullets: "Open finance first, any data as fallback", "Deterministic, explainable scores; AI reads and explains", "Embed in a day: API + hosted collection page".

---

## 10. Personas and demo assets (`scripts/generate_personas.py`)

**Generation rules:**
- Deterministic: `random.Random(42)`, with a fixed `END_DATE = 2026-09-30`.
- Full data covers 2026-04-01 to 2026-09-30.
- All institution and e-wallet names are **fictional**:

  | Country | Bank | E-wallet |
  |---|---|---|
  | ID | Bank Merapi | DompetKu |
  | PH | Bank Luzon | PeraPay |
  | VN | Ngân hàng Sông Hồng | ViMo |

  Real brands (GoPay, GCash) may be mentioned only in the pitch, never rendered in assets.
- The generator also writes the **stub extraction fixtures** for every asset (`data/personas/extracted/*.json`, holding the rows the asset actually contains), so that tests and stub mode are exact.

**Outputs:**
- `data/personas/{sari,paolo,linh}_profile.json`: customer, consent ref, and default purpose, amount and tenor
- `data/personas/{p}_open_finance.json`: provider format (§6.1)
- `data/personas/extracted/*.json`: stub fixtures
- the `demo_assets/*` files

**Bu Sari (ID, business, "Warung (grocery kiosk)", 6 years)**
- **Request:** IDR 50,000,000 over 12 months, consent ref `of-sari-001`.
- **Open finance:** Bank Merapi ••4821, **July–September 2026 only**.
  - About 12 inflows (`TRF DARI …`, settlement credits), about 15 outflows (supplier payments).
  - 2 outflows of `TOPUP DOMPETKU` IDR 500,000 that match DompetKu top-ups, which merge marks as internal transfers.
  - 1 inflow `QRIS SETTLEMENT` identical in date and amount to a row in the QRIS CSV, which merge marks as a duplicate.
  - Running balances are consistent.
  - **Result: insufficient** (3 months, about 12 inflows).
- **Assets she uploads:**
  - **`demo_assets/sari_dompetku.png`:** a phone screenshot (1080×1920, PIL). Header "DompetKu · Riwayat Transaksi", about 14 rows for September 2026.
    - Ordinary rows look like "+Rp85.000 · Terima pembayaran · 14 Sep" (in) and "−Rp120.000 · Bayar listrik · 16 Sep" (out).
    - 2 rows read "+Rp500.000 · Isi saldo dari Bank Merapi", dated the same day as, or the day after, the 2 bank `TOPUP DOMPETKU` outflows, so merge pairs them as internal transfers.
    - There is no balance column.
  - **`demo_assets/sari_qris.csv`:** semicolon-delimited, header `Tgl Transaksi;Nominal (Rp);Status;Keterangan;ID Merchant`, dates `dd-mm-yyyy`, amounts like `1.250.000`, Status `BERHASIL` (plus 3 rows `GAGAL`, which must be filtered out via `status_column`). About 150 rows from April to September 2026 (daily settlements, roughly IDR 600k–1.6M a day), with a gentle upward trend.
  - **`demo_assets/sari_buku_kas.png`:** a photo-like image (1280×960) of a lined paper ledger page on a wooden-desk background, with slight rotation (−2°) and light noise. It uses a handwriting font (download the OFL font "Caveat" from Google Fonts into `scripts/fonts/`). Columns are "Tgl | Keterangan | Masuk | Keluar", with about 18 rows for September 2026, such as "2/9 Jual beras 5kg — 75.000", "3/9 Beli gas elpiji — — 22.000" and "5/9 Cicilan koperasi — — 400.000" (that last one is a loan repayment).
  - **`demo_assets/sari_buku_kas.y4m`:** a 10 s, 15 fps, 1280×720 video of the ledger image, for the fake webcam. Generate it with `ffmpeg -loop 1 -i sari_buku_kas.png -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" -t 10 -r 15 -pix_fmt yuv420p sari_buku_kas.y4m`. Add the file to `.gitignore` if it exceeds 50 MB; the generate script recreates it.
- **Target after all uploads:** at least 6 months, at least 20 inflows, grade **A or B**, recommendation **favorable**, no tamper flags, verified share below 0.4 (so the trust component scores 3, which shows trust weighting at work). The generator **must assert this** by running `scoring.score` on the merged stub fixtures, and must adjust its parameters until the assertion holds.

**Paolo (PH, individual, "Ride-hailing driver", 3 years)**
- **Request:** PHP 80,000 over 6 months, consent ref `of-paolo-001`.
- **Open finance:** Bank Luzon ••2210 and PeraPay ••7781, April–September 2026.
  - Weekly payouts "RIDE PLATFORM PAYOUT" of PHP 3,500–9,000 with high variance.
  - Fuel and food outflows, and a monthly "LOAN HULOG" of PHP 2,500.
  - One "RETURNED – INSUFFICIENT FUNDS".
- **Target:** sufficient right away, grade **C**, recommendation **review**.

**Linh (VN, business, "Online fashion shop", 2 years)**
- **Request:** VND 150,000,000 over 12 months, consent ref `of-linh-001`.
- **Open finance:** ViMo ••5502, **August–September 2026 only**, which is thin.
- **Upload:** `demo_assets/linh_statement.pdf` (reportlab).
  - A two-page statement from "Ngân hàng Sông Hồng" covering April–September 2026, with a running balance column.
  - **2 rows tampered:** the amount was inflated, but the balances were left as originally computed.
  - 2 inflow rows with "HOÀN TRẢ" (returned payments).
  - One marketplace counterparty "SÀN TMĐT SHOPMALL" provides about 60% of inflows.
  - Volatile months, with a declining trend.
- **Target:** grade **D**, recommendation **unfavorable**, `tamper_flag_count == 2`.

The generator must assert **every** persona's target (Sari, Paolo and Linh) against the stub fixtures, and must adjust its parameters until all three assertions hold. `test_personas.py` asserts the same targets.

**Seed (`scripts/seed.py`)**
- **Client:** creates `clients/pinjamcepat` with `{name:"PinjamCepat", api_key_hash: hash(DEMO_CLIENT_API_KEY)}`.
- **Paolo:** created through the service layer (the same function the API uses). He is scored immediately.
- **Linh:** created the same way, so she gets `needs_more_data`. The seed then issues a collection link, adds her upload source from the stub fixture (not live Gemini, to make it deterministic), and completes the collection, which scores her.
- **AI summaries:** generated live unless `--no-ai` is passed.
- **Idempotent:** the seed deletes the existing seeded assessments, tagged `external_ref` starting with `SEED-`, before creating new ones.
- **Bu Sari:** **not** seeded. She is created live in the video and by judges.

**`scripts/check_gemini.py`**
- Runs live `extract_document` / `map_csv_columns` on each asset.
- Prints the row counts next to the fixture counts.
- Fails if a count differs by more than 20%, or if Sari's merged live result isn't `favorable`.

---

## 11. Testing (pytest, written test-first)

All tests use `REPO_BACKEND=memory` and `GEMINI_BACKEND=stub`. No network access.

| File | Covers |
|---|---|
| `test_scoring.py` | Each band boundary per component (parametrized). Grade cut-offs. Clamping. Tamper and limited-data downgrades. Affordability math (installment for P=50,000,000, n=12, r=1.5%/month ≈ 4,584,000; assert to the nearest unit using a precomputed value). `suggested_max_amount` when the coverage ratio is below 1.5. Window selection (the last 6 months with data). Monthly series. |
| `test_merge.py` | Duplicates across sources keep the more trusted one. No duplicate is created within the same source. Internal-transfer pairing (same day and next day; one pair per transaction). Idempotency. |
| `test_tamper.py` | Clean chain gives no flags. A modified amount gives a flag at the correct `row_index`. Rows without a balance reset the chain. Tolerance of 1. |
| `test_sufficiency.py` | Thresholds, plus duplicates and transfers being excluded. |
| `test_adapters.py` | Open-finance mapping. Standard-format validation. `csv_mapper.apply` on `sari_qris.csv` with its fixture mapping (`GAGAL` filtered out, amounts parsed). |
| `test_tokens.py` | Hashing. URL format. Expiry. |
| `test_personas.py` | Golden outcomes. Sari: insufficient before uploads, then favorable with grade A or B after the stub uploads. Paolo: C/review. Linh: D/unfavorable with 2 tamper flags. |
| `test_design.py` | Revision 2 rules: no emoji (except country flags) in `app/static/**`, `README.md`, `SUBMISSION.md`, `docs/pitch-outline.md` and `video/record_demo.ts`; the logo is served and every HTML page links the favicon; `icons.js` exports every icon name the pages use. |
| `test_ratelimit.py` | Sliding window (5/min) and recovery. Daily cap per UTC day, with midnight reset. A minute-limited call doesn't spend the daily budget. Uploads over the limit return 429 (`rate_limited` / `daily_limit_reached`) without using up an item. Summaries over the limit become `summary_failed`. Only live Gemini is wrapped. |
| `test_gemini.py` (rev 3) | Timeouts fit the Hosting limit. Extraction and `map_json` use 50 s, mapping uses 25 s. Thinking budget is 0. A fast failure retries; a slow timeout doesn't. |
| `test_deploy_scripts.py` | Local-only, so it skips on a clean clone. Scripts parse and are executable. `deploy.sh` uses `--min-instances 0 --max-instances 1 --cpu-boost`. `bootstrap.sh` has 8 steps and never touches billing (the spend cap lives in Cloud Billing). |
| `test_api.py` | TestClient tests. Client API auth (401). Create returns `needs_more_data` and a `collection_url` for Sari. Create returns `scored` for Paolo. Collect GET; invalid link 404; expired link 410 (by monkeypatching the clock); bad MIME type 422; item upload; complete then scored. The console API rejects a missing token (dependency override for valid tokens). Review accept and override. Pushing a source with `standard` and with `auto`. `frame-ancestors` header on `/c/{token}`. |

**Browser check:** `video/check_pages.ts` opens every page, including the cost slide, and fails on:
- any console error;
- a primary button whose colour is overridden;
- horizontal overflow at 375 px;
- anything other than exactly one tamper label on Linh.

**Live checks (not in CI):**
- `scripts/check_gemini.py`
- `scripts/smoke.py BASE_URL`: checks `/healthz`, creates a Paolo assessment through the API with the demo key, checks it is `scored`, and checks `GET /docs` returns 200.

---

## 12. Deployment

**One command (`bootstrap.sh <project> [region]`).** After billing is linked and the user has run `gcloud auth login`, `gcloud auth application-default login` and `npx firebase-tools@13 login`, `bootstrap.sh` does all setup and then calls `deploy.sh`:
- checks billing and enables the APIs
- adds Firebase and the Hosting site
- registers the web app and writes `.env.deploy` (generated demo keys, `chmod 600`)
- grants the default compute service account `roles/run.builder` for source deploys
- waits until Google sign-in is enabled. This is the only console click, because Google doesn't allow creating that provider's OAuth client from a CLI.
- runs `scripts/check_gemini.py`, then deploys

It is idempotent. `deploy.sh` alone redeploys code changes.

**Cost guardrails.**
- **One instance:** Cloud Run runs with `--max-instances 1`, so a flood queues or fails instead of scaling out.
- **Five Gemini calls per minute:** `RateLimitedGemini` wraps the live Gemini backend with a 60-second sliding window (`GEMINI_RPM`, default 5). With a single instance this is a global limit. When the limit is hit:
  - uploads and pushed JSON return `429 rate_limited` without using up an item;
  - summaries degrade to `summary_failed`, and the analyst can use Regenerate summary.
- **50 Gemini calls per day:** a daily cap (`GEMINI_DAILY_CAP`, default 50, about 12 full Sari demos) is checked after the per-minute limit. It's counted in Firestore (`usage/gemini-YYYY-MM-DD`, a transactional increment), so instance restarts don't reset it. It resets at 00:00 UTC. Once reached, uploads return `429 daily_limit_reached`, and the collection page explains it in the customer's language.
- **No Vertex-side cap:** Gemini 2.5 Flash uses Dynamic Shared Quota, so there's no per-project quota to lower.
- **Spend cap:** a $10/month spend cap and budget alerts (50/90/100%, credits excluded) are set by the owner in the Cloud Billing console. `bootstrap.sh` doesn't touch billing.

**`Dockerfile`**
- Base image `python:3.12-slim`; `pip install -r requirements.txt`.
- Copy `app/`, `data/` and `demo_assets/`, excluding the y4m.
- `CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

**`deploy.sh`** (idempotent; `PROJECT` and `REGION` are its arguments):
1. `gcloud config set project $PROJECT`. Enable `run`, `firestore`, `aiplatform`, `cloudbuild`, `artifactregistry`, `iamcredentials`, `firebase` and `identitytoolkit`.
2. Create Firestore if it's missing: `gcloud firestore databases create --location=$REGION` (Native mode).
3. Create the service account `kasflow-run` and grant it:
   - `roles/datastore.user` and `roles/aiplatform.user`
   - `roles/firebaseauth.admin` (for custom tokens and token verification)
   - `roles/iam.serviceAccountTokenCreator` **on itself**
4. Deploy to Cloud Run:
   ```
   gcloud run deploy kasflow --source . --region $REGION --service-account kasflow-run@… \
     --allow-unauthenticated --min-instances 0 --max-instances 1 --cpu-boost --timeout 300 --memory 1Gi \
     --set-env-vars GOOGLE_CLOUD_PROJECT=…,GOOGLE_CLOUD_LOCATION=…,GEMINI_MODEL=…,PUBLIC_BASE_URL=…,FIREBASE_WEB_…=…,REPO_BACKEND=firestore,GEMINI_BACKEND=vertex \
     --set-env-vars DEMO_CLIENT_API_KEY=…,DEMO_LOGIN_KEY=…
   ```
   Plain environment variables are acceptable for the hackathon. Secret Manager is noted as a production improvement in the README.
5. `firebase deploy --only hosting,firestore:rules --project $PROJECT`.
6. `python scripts/seed.py`, then `python scripts/smoke.py https://$PROJECT.web.app`.

**`firebase.json`:**
```json
{ "hosting": { "public": "hosting_public", "rewrites": [ { "source": "**", "run": { "serviceId": "kasflow", "region": "<REGION>" } } ] },
  "firestore": { "rules": "firestore.rules" } }
```
`hosting_public/` contains only an empty `.gitkeep`; everything is served by Cloud Run.

**Region.** Prefer `asia-southeast1`. **Before deploying, check that Firebase Hosting → Cloud Run rewrites support the chosen region.** If not, use `us-central1` for Cloud Run. Firestore and Vertex can stay in their own locations.

**Manual Firebase console steps** (listed in the README):
1. Add Firebase to the GCP project.
2. Create a Web app to get the web config values.
3. Enable the Google sign-in provider.
4. Make sure `<project>.web.app` and `<project>.firebaseapp.com` are on the authorized domains list.

**Scale to zero (cost).** `--min-instances 0` lets Cloud Run stop the service when idle; the next request starts it again after a cold start of a few seconds (`--cpu-boost` shortens it). The frontend never polls, so idle tabs cost nothing. Do not delete the project or rotate keys until evaluation ends.

---

## 13. Video (`video/`)

**Setup**
- `record_demo.ts` is run with `npx tsx record_demo.ts` (using `playwright` directly rather than the test runner).
- Chromium launch options:
  ```ts
  chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
    "--use-file-for-fake-video-capture=../demo_assets/sari_buku_kas.y4m"], slowMo: 120 })
  ```
- Context options: `{ viewport: {width:1280,height:720}, recordVideo: {dir:"out/", size:{width:1280,height:720}}, permissions:["camera"] }`.
- `BASE_URL` and `DEMO_LOGIN_KEY` come from the environment.
- **Use one context and one page for the whole run**, so the output is a single webm.

**Helpers**
- **`caption(page, text)`:** removes any existing caption, then injects a fixed bottom-centre bar (navy `#1E3A5F` at 92% opacity, white 20 px text, square corners, a 3 px `#3FA37A` left border, `pointer-events: none` so it never blocks clicks). It must be re-applied after every `goto`, so wrap navigation in a `go(url, caption)` helper.
- **`pause(ms)`:** reading time for viewers. This is allowed only in the video script.
- **Waits:** always `await expect(locator).toBeVisible({timeout: 60000})`, never fixed waits for app state.

**Scenes**
- **Length:** the local stub-mode recording measures 3:37. A live run adds a few seconds.
- **Pacing:** `BASE_PACE` 1.65 stretches all pauses, and `PACE` fine-tunes so the total lands between 3:00 and 4:00.
- **Narration:** `docs/voiceover-script.md`, timed to these captions.

| # | Scene | Actions | Caption(s) |
|---|---|---|---|
| 1 | Intro | `go(/demo/intro)`, pause 12 s | "KasFlow — credit signals from any data" |
| 2 | Client applies | `go(/demo/client)`, Sari persona, Connect accounts → consent modal → Allow; wait for the API log response with `needs_more_data`; scroll the log | "A client app (PinjamCepat) calls the KasFlow API with open-finance consent" → "Open-finance data is thin: KasFlow asks for more, via an embeddable page" |
| 3 | Upload | `frameLocator('#kasflow-frame')`: `setInputFiles` on `sari_dompetku.png`, wait for "transaksi terbaca"; then `sari_qris.csv` | "Customer adds an e-wallet screenshot and a QRIS export — Gemini reads any format" |
| 4 | Camera | Click "Ambil foto", wait 2 s for the preview (fake webcam showing the ledger), click "Ambil", wait for the item status "done"; close the modal | "No digital records? Photograph the paper cash book — Gemini reads handwriting" |
| 5 | Done | Click "Selesai"; wait for the parent page to show "Data diterima"; wait for the API log to show `scored` | "Re-scored automatically; the client gets the result by API" |
| 6 | Console | `go(/demo-login?key=…)`, which redirects to `/console`; open Bu Sari's row | "Analysts review in the KasFlow console (Google sign-in)" |
| 7 | Sources | Scroll to the sources panel; expand the bank source to show the duplicate and internal-transfer rows | "4 sources merged: verified vs AI-extracted, duplicates & transfers removed" |
| 8 | Result | Scroll to the score, chart and AI summary; click one metric chip; toggle the customer explanation between local and EN | "Deterministic score + Gemini explanation that cites its metrics" |
| 9 | Review | Click Accept and Submit; the review card appears | "Human-in-the-loop decision, fully audited" |
| 10 | Tamper | Back to the list; open Linh; expand the upload source showing red tampered rows; show **unfavorable** | "Edited PDF? Balance arithmetic exposes tampering" |
| 11 | API docs | `go(/docs)`, scroll slowly | "Any company integrates via REST API" |
| 12 | Cost | `go(/demo/cost)`, pause 10 s | "Under 2 US cents per credit assessment, measured live" |
| 13 | Outro | `go(/demo/outro)`, pause 12 s | "Built on Gemini · Cloud Run · Firestore · Firebase" |

**`stitch.sh`**
- Converts `out/*.webm` to `kasflow-demo.mp4` (`ffmpeg -i in.webm -c:v libx264 -pix_fmt yuv420p -crf 20`).
- Reads the duration with `ffprobe`.
- Exits non-zero if the duration is under 180 s or over 240 s, printing the actual duration.

---

## 14. Submission artifacts

**`README.md`**
- One-paragraph pitch.
- A mermaid architecture diagram.
- **How to evaluate:**
  - Open `https://<project>.web.app/demo/client` and run the Sari flow; on a phone, use the console's QR code to try the camera.
  - Then open `/` and sign in with any Google account to see the console.
  - The API docs are at `/docs`.
- Local development: `REPO_BACKEND=memory GEMINI_BACKEND=stub uvicorn app.main:app`.
- Tests, deploy, and the production-readiness notes:
  - real rails (Indonesia's BI SNAP open API, the Philippines Open Finance PH, and others)
  - webhooks
  - per-client tenancy and analyst invites
  - Secret Manager
  - rate limiting
- **Deployment:** how each Google service is used. No step-by-step commands, because the scripts are local-only.
- **Cost per assessment:** a measured table per persona (Gemini calls, tokens, Gemini cost, infrastructure cost, total), where the cost comes from, the cost at scale, and the demo guardrails.

**`SUBMISSION.md`**
- A brief description of about 200 words, including the measured cost per assessment (US$0.002–0.018).
- An explicit paragraph each for **Firebase** (Auth and Hosting), **Firestore**, **Cloud Run** and **Gemini**, using the roles in §1.

**`docs/voiceover-script.md`:** a narration script for the video, with one part per caption-timed scene, optional lines, and recording tips.

**`docs/pitch-outline.md`**: content for each slide, to paste into the organiser's template. No emoji in any of these documents (§9.0).
1. **Problem:** the US$2.5T APAC MSME credit gap (ADB 2024); thin-file customers.
2. **Insight:** the data exists but is scattered (open finance, e-wallets, QRIS, paper).
3. **Solution:** KasFlow, credit signals from any data.
4. **How it works:** a diagram.
5. **Demo** screenshots.
6. **Trust and safety:** consent references; tokenized, expiring links; files not stored; deterministic scoring; tamper detection; human-in-the-loop; no protected attributes.
7. **Google stack:** Gemini, Cloud Run, Firestore, Firebase.
8. **Business model:** a per-assessment B2B fee; embeddable within a day.
9. **Market:** SEA lending companies, BNPL, rental and insurance.
10. **Roadmap:** real rails, webhooks, more document types, fairness monitoring.
11. **Team.**

---

## 15. Build order (milestones for the implementation plan)

1. **Scaffold.** Repo, `requirements.txt`, `app/main.py` with `/healthz`, config, models, and `InMemoryRepo`.
2. **Pure core, test-first.** `scoring`, `merge`, `tamper`, `sufficiency`, `tokens`, adapters, `csv_mapper`.
3. **Personas.** `generate_personas.py` with the fixtures and assets, plus `test_personas.py` passing in stub mode.
4. **Pipeline and APIs.** Client API, collect API, console API and demo endpoints, plus `test_api.py`.
5. **Gemini.** Live `gemini.py` (Vertex), with `check_gemini.py` passing against the real API.
6. **Frontend.** Console, collection page, demo client, intro and outro, and the login pages.
7. **Deploy.** Firestore repo, Firebase config, `deploy.sh`, seed, and smoke test against the deployed URL.
8. **Video.** Record, stitch, and confirm the duration check passes.
9. **Docs.** `README.md`, `SUBMISSION.md`, `pitch-outline.md`.

Milestones 1–4 run entirely offline (stub and memory), so the app is usable locally before any GCP setup exists.
