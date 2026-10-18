# Access checklist (Phase B)

Everything in this repo runs locally without Google Cloud access. Defaults: `REPO_BACKEND=memory`, `GEMINI_BACKEND=stub`, `AUTH_BACKEND=stub`.
The items below are needed to deploy. Provide them, then run the Phase B commands in order.

## 1. What you do by hand (about 10 minutes)
| # | What | How |
|---|---|---|
| 1 | Create a GCP project and **link billing** (the US$300 free trial works) | [console.cloud.google.com](https://console.cloud.google.com) → New project; Billing → Link a billing account |
| 2 | Log in to gcloud (your user needs Owner on the project) | `gcloud auth login` |
| 3 | Application Default Credentials (local scripts call Vertex and Firestore) | `gcloud auth application-default login` |
| 4 | Log in to the Firebase CLI | `npx firebase-tools@13 login` |
| 5 | Run the bootstrap; when it pauses, enable **Google** sign-in in the Firebase console (one click, link printed) | `./bootstrap.sh <project-id>` |
| 6 | ffmpeg for the mp4 (already installed) | `brew install ffmpeg` |
| 7 | A GitHub repo for the submission | `gh repo create kasflow --public --source . --push` |

`gcloud` comes from `brew install --cask gcloud-cli` if a machine doesn't have it.

## 2. What `bootstrap.sh` does for you
Safe to re-run; each step skips work that's already done.
1. Checks the tools, the three logins and that billing is linked (with a direct link if it isn't).
2. Enables every API: Cloud Run, Firestore, Vertex AI, Cloud Build, Artifact Registry, IAM Credentials, Identity Toolkit, Firebase, Firebase Hosting, Compute.
3. Adds Firebase to the project and creates the `<project>.web.app` Hosting site.
4. Registers the Firebase web app and writes `.env.deploy` (gitignored, `chmod 600`) with its config and freshly generated `DEMO_CLIENT_API_KEY` / `DEMO_LOGIN_KEY`. Existing keys are kept on re-runs.
5. Grants the default compute service account `roles/run.builder`, which source deploys need in newer projects.
6. Waits until Google sign-in is enabled (it checks through the Identity Toolkit API). Authorized domains `<project>.web.app` and `<project>.firebaseapp.com` are added by Firebase automatically.
7. Runs `scripts/check_gemini.py` against live Vertex Gemini. If anything is off it asks before deploying; changing `GEMINI_MODEL` in `.env.deploy` fixes model-availability errors.
8. Runs `./deploy.sh <project> <region>`: Firestore database, `kasflow-run` service account and roles, Cloud Run (scales to zero), Hosting + Firestore rules, seeding and a smoke test.

It finishes by printing the demo URLs and the private demo-login link used for the video.

**Region.** The default is `asia-southeast1`. If the Hosting deploy rejects rewrites to Cloud Run there, re-run with `./bootstrap.sh <project-id> us-central1`.

**If something fails.**
- `projects:addfirebase` says terms not accepted: open [console.firebase.google.com](https://console.firebase.google.com) once, accept the terms, re-run.
- Cloud Build permission errors on the first deploy: wait a minute (IAM propagation) and re-run.

## 3. After it's deployed
1. Open `https://<project>.web.app/demo/client` once (wakes the instance) and run the Sari flow. Then sign in at `/` with Google.
2. Record: `cd video && BASE_URL=https://<project>.web.app DEMO_LOGIN_KEY=<from .env.deploy> npx tsx record_demo.ts && ./stitch.sh`. If the duration is out of range, re-record with `PACE=1.15` (longer) or `PACE=0.9` (shorter). A local stub-mode run measured 3:20; live Gemini adds a few seconds per upload, so start with `PACE=0.95` if the first live take runs long. A stub-mode take exists locally in `video/out/` as a fallback.
3. Push to GitHub; fill in the deck from `docs/pitch-outline.md`; paste `SUBMISSION.md`; narrate with `docs/voiceover-script.md`.

To deploy code changes later, `./deploy.sh <project-id>` alone is enough.

## 4. Code paths that only Phase B verifies
| Code | Covered locally by | Verified live by |
|---|---|---|
| `FirestoreRepo` (`app/repo.py`) | Same interface as `InMemoryRepo` (all tests) | `deploy.sh` → `seed.py` + `smoke.py` |
| `VertexGemini` real calls | Fake-client unit tests | `scripts/check_gemini.py` |
| `FirebaseVerifier` + custom tokens | Monkeypatched unit test | Console sign-in; `/demo-login` in the recorded video |
| `bootstrap.sh`, `deploy.sh`, `firebase.json` rewrite | `bash -n` (tests), `docker build` | `bootstrap.sh` run |

## 5. Keep it alive during evaluation
- Cloud Run scales to zero (`--min-instances 0`), so you pay nothing while it is idle. The first request after idle waits a few seconds for a cold start; open the demo URL once right before presenting or recording. The console never auto-refreshes, so a forgotten browser tab doesn't keep an instance running.
- Don't delete the project, rotate the demo keys, or disable billing until evaluation ends.
- Collection links expire after 72 hours. Judges create fresh ones from `/demo/client`.
