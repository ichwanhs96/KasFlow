# Access checklist (Phase B)

Everything in this repo runs locally without Google Cloud access. Defaults: `REPO_BACKEND=memory`, `GEMINI_BACKEND=stub`, `AUTH_BACKEND=stub`.
The items below are needed to deploy. Provide them, then run the Phase B commands in order.

## 1. Access and accounts to provide
| # | What | Why | How to check |
|---|---|---|---|
| 1 | A GCP project with billing enabled (e.g. `kasflow-hack`) | Cloud Run, Firestore, Vertex AI | `gcloud projects describe <id>` |
| 2 | Your gcloud user with Owner (or Editor + Project IAM Admin + Service Account Admin) on the project | `deploy.sh` enables APIs, creates the service account and grants roles | `gcloud auth login` |
| 3 | Application Default Credentials for local scripts | `check_gemini.py` and `seed.py` call Vertex and Firestore from your laptop | `gcloud auth application-default login` |
| 4 | Vertex AI Gemini access in `GOOGLE_CLOUD_LOCATION` (default `us-central1`), with the chosen `GEMINI_MODEL` available | Extraction, CSV/JSON mapping, summaries | `scripts/check_gemini.py` |
| 5 | Firebase added to the GCP project | Hosting + Auth | Firebase console → Add project → select the existing GCP project |
| 6 | A Firebase **Web app** registered; copy its `apiKey`, `authDomain`, `projectId` and `appId` | Browser sign-in config (`/config.js`) | Firebase console → Project settings → Your apps |
| 7 | **Google** sign-in provider enabled | Analyst login | Firebase console → Authentication → Sign-in method |
| 8 | Authorized domains include `<project>.web.app` and `<project>.firebaseapp.com` | Popup sign-in on the hosted URL | Authentication → Settings → Authorized domains |
| 9 | Firebase CLI login | `firebase deploy` | `npx firebase-tools@13 login` |
| 10 | Region choice | Firebase Hosting must support rewrites to Cloud Run in the region | Default `asia-southeast1`; if the Hosting deploy rejects it, re-run with `us-central1` |
| 11 | ffmpeg installed locally | `video/stitch.sh` (mp4 + duration check) | `brew install ffmpeg` |
| 12 | A GitHub repo (public, or accessible to judges) plus `gh auth login` | Submission | `gh repo create kasflow --public --source . --push` |

## 2. `.env.deploy` (create it in the repo root; never commit it)
```
GOOGLE_CLOUD_LOCATION=us-central1
GEMINI_MODEL=gemini-2.5-flash
DEMO_CLIENT_API_KEY=<openssl rand -hex 16>
DEMO_LOGIN_KEY=<openssl rand -hex 16>
FIREBASE_WEB_API_KEY=<from item 6>
FIREBASE_WEB_AUTH_DOMAIN=<project>.firebaseapp.com
FIREBASE_WEB_PROJECT_ID=<project>
FIREBASE_WEB_APP_ID=<from item 6>
```
Before recording, check whether Vertex has a newer GA Gemini Flash model. If it does, set `GEMINI_MODEL` to it. No code change is needed.

## 3. Phase B run order
1. `export GOOGLE_CLOUD_PROJECT=<project> GOOGLE_CLOUD_LOCATION=us-central1 GEMINI_MODEL=gemini-2.5-flash`
2. `.venv/bin/python scripts/check_gemini.py`. Every line must say OK. If a count is off, tune `app/services/prompts.py` and re-run.
3. `./deploy.sh <project> asia-southeast1`. It deploys Cloud Run and Hosting, seeds Firestore and runs the smoke test.
4. Open `https://<project>.web.app/demo/client` and run the Sari flow. Then sign in at `/` with Google.
5. Record: `cd video && BASE_URL=https://<project>.web.app DEMO_LOGIN_KEY=<key> npx tsx record_demo.ts && ./stitch.sh`. If the duration is out of range, re-record with `PACE=1.15` (longer) or `PACE=0.9` (shorter). For reference, a local stub-mode run measured 3:20; live Gemini calls add some seconds per upload, so start with `PACE=0.95` if the first live take runs long. A stub-mode take already exists locally in `video/out/` (gitignored) as a fallback.
6. Push to GitHub; fill in the deck from `docs/pitch-outline.md`; paste `SUBMISSION.md`.

## 4. Code paths that only Phase B verifies
| Code | Covered locally by | Verified live by |
|---|---|---|
| `FirestoreRepo` (`app/repo.py`) | Same interface as `InMemoryRepo` (all tests) | `deploy.sh` → `seed.py` + `smoke.py` |
| `VertexGemini` real calls | Fake-client unit tests | `scripts/check_gemini.py` |
| `FirebaseVerifier` + custom tokens | Monkeypatched unit test | Console sign-in; `/demo-login` in the recorded video |
| `deploy.sh`, `firebase.json` rewrite | `bash -n`, `docker build` | `deploy.sh` run |

## 5. Keep it alive during evaluation
- Cloud Run scales to zero (`--min-instances 0`), so you pay nothing while it is idle. The first request after idle waits a few seconds for a cold start; open the demo URL once right before presenting or recording. The console never auto-refreshes, so a forgotten browser tab doesn't keep an instance running.
- Don't delete the project, rotate the demo keys, or disable billing until evaluation ends.
- Collection links expire after 72 hours. Judges create fresh ones from `/demo/client`.
