# KasFlow — brief description

KasFlow is credit-scoring infrastructure for Southeast Asia's thin-file customers: micro-businesses and individuals
whose financial history is scattered across bank accounts, e-wallets, QRIS settlements and handwritten cash books.
A client company (lending, BNPL, rental or insurance) calls one API. KasFlow fetches open-finance data first. If that
isn't enough, it returns a secure, expiring collection link that the client embeds in its own app. There, customers upload
statements or screenshots, or photograph paper ledgers with their camera. KasFlow merges every source, tags each
transaction as verified or AI-extracted, removes duplicates and internal transfers, and detects edited statements
through running-balance arithmetic. A deterministic engine produces an explainable score, and analysts make the final call.

**Gemini.** Gemini (on Vertex AI) does three jobs:
1. Multimodal extraction of transactions from PDFs, e-wallet screenshots and camera photos of handwritten ledgers.
2. Schema mapping for unknown CSV/JSON formats from any partner system.
3. An analyst summary in which every point cites a metric, plus an explanation for the customer in Bahasa Indonesia,
   Filipino or Vietnamese.

Gemini never computes the score.

**Cloud Run.** The entire backend — REST API, pipeline and the web UI — runs as one container on Cloud Run that
scales to zero when idle, so the demo costs nothing between visits.

**Firestore.** Firestore stores clients, assessments, normalized transactions and a complete audit trail of every
client, customer, system and analyst action. Browser access is denied by security rules; all access goes through the backend.

**Firebase.** Firebase Authentication provides Google sign-in for analysts, plus custom tokens for automated demo
login. Firebase Hosting is the public front door and rewrites to Cloud Run.
