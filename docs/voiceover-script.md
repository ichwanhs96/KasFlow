# KasFlow demo: voice-over script

Read this over `video/kasflow-demo.mp4` (3:20). Each part starts when its on-screen caption appears.

- **Pace:** calm, about 140 words per minute. Each part fits its scene with a little breathing room.
- **Pauses:** `/` marks a short pause.
- **Optional lines:** text in *[brackets]* is optional and can be cut if you run long.

| # | Time | On screen |
|---|---|---|
| 1 | 0:00–0:20 | Intro card |
| 2 | 0:20–0:35 | PinjamCepat: Connect accounts, consent, Allow |
| 3 | 0:35–0:47 | Embedded KasFlow page appears; API log scrolls |
| 4 | 0:47–0:59 | E-wallet screenshot and QRIS CSV upload |
| 5 | 0:59–1:16 | Camera captures the paper cash book |
| 6 | 1:16–1:29 | Done: "Data diterima"; API log shows `scored` |
| 7 | 1:29–1:35 | Analyst console list |
| 8 | 1:35–1:50 | Sources panel; bank source expanded |
| 9 | 1:50–2:20 | Score, metrics, chart, AI summary, customer explanation |
| 10 | 2:20–2:29 | Analyst review submitted |
| 11 | 2:29–2:47 | Linh: tamper flags, unfavorable |
| 12 | 2:47–3:01 | API docs |
| 13 | 3:01–3:20 | Outro card |

---

### 1. Intro (0:00–0:20)
> Across Asia-Pacific, small businesses face a credit gap of around two and a half trillion dollars. / In Southeast Asia, their financial history isn't missing. It's scattered across banks, e-wallets, QRIS payments / and paper cash books. / This is KasFlow: credit signals from any data.

### 2. A client applies (0:20–0:35)
> PinjamCepat is a lending app that uses KasFlow. / Bu Sari runs a warung in Indonesia. She connects her accounts through open finance / and gives consent. / PinjamCepat's backend makes a single call to the KasFlow API.

### 3. Not enough data (0:35–0:47)
> KasFlow fetches her open-finance data first. / But it only covers three months, so KasFlow returns a secure collection link / and PinjamCepat embeds it right inside its own app. / No login, and it expires in seventy-two hours.

### 4. Uploads (0:47–0:59)
> Sari adds what she has: / a screenshot from her e-wallet, / and a QRIS settlement export. / Gemini reads any format. Images, PDFs, CSVs with columns it has never seen.

### 5. Camera (0:59–1:16)
> Much of her business still lives on paper. / So she simply photographs her handwritten cash book. / Gemini reads the handwriting and turns every line into a transaction. / *[Each file shows how many transactions were read, so she knows it worked.]*

### 6. Re-scored (1:16–1:29)
> When she taps "Selesai", KasFlow merges everything and scores her again, automatically. / PinjamCepat is notified, and gets the result back through the API, / including a plain-language explanation for Sari.

### 7. The analyst console (1:29–1:35)
> On the other side, analysts review every assessment in the KasFlow console.

### 8. Sources (1:35–1:50)
> Four sources, merged into one picture. / Open-finance data is marked as verified, uploads as extracted by AI. / Duplicates across sources and transfers between her own accounts are detected and excluded, / so nothing is counted twice.

### 9. Score and AI summary (1:50–2:20)
> The score itself is deterministic. / Plain Python computes cash-flow stability, margin, trend, returned payments, debt burden and data trust, / and the same data always gives the same result. / *[Sari's thin file becomes a favorable grade A.]* / Gemini never decides the score. It explains it. / Every strength and risk cites the exact metric behind it. One click takes you there. / And the customer gets the same explanation in her own language.

### 10. Review (2:20–2:29)
> A human makes the final call. / The analyst accepts or overrides, / and every step is recorded in the audit trail.

### 11. Tampering (2:29–2:47)
> Now Linh, an online shop owner in Vietnam. / She uploaded a bank statement with inflated amounts. / KasFlow checks the running balance on every row, / and the arithmetic doesn't add up. / Two rows are flagged, and the assessment comes back unfavorable.

### 12. API (2:47–3:01)
> Any company can integrate KasFlow, whether lending, BNPL, rental or insurance. / Create an assessment, push extra data, / or embed the hosted collection page. / It's a simple REST API.

### 13. Outro (3:01–3:20)
> KasFlow: open finance first, any data as fallback, even paper. / Deterministic, explainable scores, with AI that reads and explains. / Built on Gemini, Cloud Run, Firestore and Firebase. / Credit signals from any data.

---

## Recording tips
- Record each part as its own take so you can slide it onto the caption in the editor.
- If a part runs long, cut the *[bracketed]* line first, then shorten the pause before the last sentence.
- Part 9 is the longest scene (30 s). If you end early, let the AI-summary panel breathe on screen; don't fill the gap.
- **Stub mode:** this local take was recorded in stub mode, so its AI-summary text is a placeholder that reads "stub summary, Gemini not called". After deploying with real Gemini (ACCESS.md, Phase B step 5), re-record the video for submission. The scene order is the same, so this script still fits; just recheck the timings against the new captions.
