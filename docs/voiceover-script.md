# KasFlow demo: voice-over script

Read this over `video/kasflow-demo.mp4` (3:37). Each part starts when its on-screen caption appears.

- **Timing:** the times below were measured from the captions in the current recording.
- **Pace:** calm, about 140 words per minute. Each part fits its scene with a little breathing room.
- **Pauses:** `/` marks a short pause.
- **Optional lines:** text in *[brackets]* is optional and can be cut if you run long.

| # | Time | On screen |
|---|---|---|
| 1 | 0:00–0:20 | Intro card |
| 2 | 0:20–0:34 | PinjamCepat: Connect accounts, consent, Allow |
| 3 | 0:34–0:47 | Embedded KasFlow page appears; API log scrolls |
| 4 | 0:47–0:59 | E-wallet screenshot and QRIS CSV upload |
| 5 | 0:59–1:15 | Camera captures the paper cash book |
| 6 | 1:15–1:28 | Done: "Data diterima"; API log shows `scored` |
| 7 | 1:28–1:35 | Analyst console list |
| 8 | 1:35–1:49 | Sources panel; bank source expanded |
| 9 | 1:49–2:19 | Score, metrics, chart, AI summary, customer explanation |
| 10 | 2:19–2:29 | Analyst review submitted |
| 11 | 2:29–2:45 | Linh: tamper flags, unfavorable |
| 12 | 2:45–2:59 | API docs |
| 13 | 2:59–3:17 | Cost per assessment |
| 14 | 3:17–3:37 | Outro card |

---

### 1. Intro (0:00–0:20)
> Across Asia-Pacific, small businesses face a credit gap of around two and a half trillion dollars. / In Southeast Asia, their financial history isn't missing. It's scattered across banks, e-wallets, QRIS payments / and paper cash books. / This is KasFlow: credit signals from any data.

### 2. A client applies (0:20–0:34)
> PinjamCepat, a lending app, uses KasFlow. / Bu Sari runs a warung in Indonesia. She connects her accounts through open finance and gives consent. / PinjamCepat makes one call to the KasFlow API.

### 3. Not enough data (0:34–0:47)
> KasFlow fetches her open-finance data first. / It only covers three months, so KasFlow returns a secure link / that PinjamCepat embeds in its own app. / No login needed.

### 4. Uploads (0:47–0:59)
> Sari adds what she has: / an e-wallet screenshot / and a QRIS settlement export. / Gemini reads any format: images, PDFs, CSVs it has never seen.

### 5. Camera (0:59–1:15)
> Much of her business still lives on paper. / So she simply photographs her handwritten cash book. / Gemini reads the handwriting and turns every line into a transaction. / *[Each file shows how many transactions were read, so she knows it worked.]*

### 6. Re-scored (1:15–1:28)
> When she taps "Selesai", KasFlow merges everything and scores her again, automatically. / PinjamCepat is notified, and gets the result back through the API, / including a plain-language explanation for Sari.

### 7. The analyst console (1:28–1:35)
> On the other side, analysts review every assessment in the KasFlow console.

### 8. Sources (1:35–1:49)
> Four sources, merged into one picture. / Open-finance data is marked verified; uploads, extracted by AI. / Duplicates and transfers between her own accounts are detected and excluded, / so nothing is counted twice.

### 9. Score and AI summary (1:49–2:19)
> The score itself is deterministic. / Plain Python computes cash-flow stability, margin, trend, returned payments, debt burden and data trust, / and the same data always gives the same result. / *[Sari's thin file turns into a favorable result.]* / Gemini never decides the score. It explains it. / Every strength and risk cites the exact metric behind it. One click takes you there. / And the customer gets the same explanation in her own language.

### 10. Review (2:19–2:29)
> A human makes the final call. / The analyst accepts or overrides, / and every step is recorded in the audit trail.

### 11. Tampering (2:29–2:45)
> Linh, an online shop owner in Vietnam. / Her bank statement has inflated amounts. / KasFlow checks the running balance on every row, / and the arithmetic doesn't add up. / Two rows are flagged, and the result is unfavorable.

### 12. API (2:45–2:59)
> Any company can integrate KasFlow, whether lending, BNPL, rental or insurance. / Create an assessment, push extra data, / or embed the hosted collection page. / It's a simple REST API.

### 13. Cost per assessment (2:59–3:17)
> And it's cheap to run. / Measured live, an assessment costs about a fifth of a cent when open-finance data is enough, / under one cent with uploads and a camera photo, / and under two cents for a long bank statement. / *[The scoring itself is plain Python, so there's no AI cost there.]*

### 14. Outro (3:17–3:37)
> KasFlow: open finance first, any data as fallback, even paper. / Deterministic, explainable scores, with AI that reads and explains. / Built on Gemini, Cloud Run, Firestore and Firebase. / Credit signals from any data.

---

## Recording tips
- Record each part as its own take so you can slide it onto its caption in the editor.
- If a part runs long, cut the *[bracketed]* line first, then shorten the pause before the last sentence.
- **Fit:** read at about 140 words per minute, every part's main text fits its scene. In parts 5 and 13 the bracketed line only fits if you read briskly, so skip it otherwise.
- Part 9 is the longest scene (30 s). If you finish early, let the AI-summary panel stay on screen without filling the gap.
- **Stub mode:** the current recording was made in local stub mode, so its AI-summary panel shows placeholder text ("stub summary, Gemini not called"). After deploying with real Gemini, re-record the video for submission:
  ```
  cd video && BASE_URL=https://<project>.web.app DEMO_LOGIN_KEY=<from .env.deploy> npx tsx record_demo.ts && ./stitch.sh
  ```
  Open the site once first so the cold start isn't in the recording. Live Gemini adds a few seconds to the upload and summary scenes (parts 4–6). The scene order and narration stay the same; just nudge each part to its caption in the editor.
- **Rate limits:** the deployed demo allows 5 Gemini calls per minute and 50 per day. A full recording uses 4 calls, so wait a minute between takes.
