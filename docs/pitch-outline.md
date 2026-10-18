# Pitch deck content (paste into the organiser's template)

1. **Problem.** Asia-Pacific MSMEs face a ~US$2.5T credit gap (ADB, 2024), and nearly half are unserved or underserved.
   Thin-file customers get declined or overcharged.
2. **Insight.** The data exists, but it's scattered: open-finance feeds, e-wallets, QRIS settlements, and paper cash books.
   Lending, BNPL, rental and insurance providers can't read it at small-ticket economics.
3. **Solution.** KasFlow, credit signals from any data. One API with open finance first and anything else as fallback,
   and a deterministic, explainable score.
4. **How it works.** Client API → open-finance fetch → sufficiency check → embeddable collection page (upload or camera)
   → Gemini extraction → merge, dedupe and tamper check → score → AI explanation → analyst review → result by API.
5. **Demo.** Screenshots: PinjamCepat embed, camera capture of a buku kas, sources panel with trust badges, score with
   AI summary, Linh's tamper flags.
6. **Trust and safety.**
   - Consent reference on every assessment.
   - Tokenized links that expire after 72 hours.
   - Uploaded files are discarded after extraction.
   - Deterministic scoring, tamper detection and human-in-the-loop review.
   - No protected attributes are used.
   - Full audit trail.
7. **Google stack.** Gemini (multimodal extraction, mapping, explanations), Cloud Run, Firestore, Firebase Auth and Hosting.
8. **Business model.** A B2B per-assessment fee, with volume tiers. Embedding takes about a day: API + hosted page.
9. **Market.** SEA lending companies, BNPL, multifinance, rental platforms and insurers. Start with Indonesia, the Philippines and Vietnam.
10. **Roadmap.** Real rails (BI SNAP, Open Finance PH), webhooks, more document types, fairness monitoring, per-client tenancy.
11. **Team.**
