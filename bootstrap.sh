#!/usr/bin/env bash
# One-command Phase B setup + deploy. Usage: ./bootstrap.sh <PROJECT_ID> [REGION]
#
# Prerequisites (one-time logins):
#   gcloud auth login
#   gcloud auth application-default login
#   npx firebase-tools@13 login
# and billing linked to the project. Safe to re-run: every step skips work that is already done.
set -euo pipefail
cd "$(dirname "$0")"

PROJECT="${1:?usage: ./bootstrap.sh <PROJECT_ID> [REGION]}"
REGION="${2:-asia-southeast1}"
FB=(npx --yes firebase-tools@13)
PY=.venv/bin/python

step() { printf '\n== %s\n' "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
json() { "$PY" -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1], {'json': json}, {'d': d}) or '')" "$1"; }

step "1/8 Checking tools and logins"
command -v gcloud >/dev/null || die "gcloud not found. Install it: brew install --cask gcloud-cli"
command -v npx >/dev/null || die "npx not found. Install Node (e.g. via nvm)."
command -v openssl >/dev/null || die "openssl not found."
[ -x "$PY" ] || die "Python venv missing. Run: uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt"
gcloud auth print-access-token >/dev/null 2>&1 || die "Not logged in to gcloud. Run: gcloud auth login"
gcloud auth application-default print-access-token >/dev/null 2>&1 \
  || die "No Application Default Credentials. Run: gcloud auth application-default login"
"${FB[@]}" login:list 2>/dev/null | grep -qi "logged in as" || die "Not logged in to Firebase. Run: npx firebase-tools@13 login"
gcloud config set project "$PROJECT" >/dev/null
gcloud auth application-default set-quota-project "$PROJECT" >/dev/null 2>&1 || true

step "2/8 Checking billing"
gcloud services enable cloudbilling.googleapis.com serviceusage.googleapis.com >/dev/null
[ "$(gcloud billing projects describe "$PROJECT" --format='value(billingEnabled)' 2>/dev/null)" = "True" ] \
  || die "Billing is not linked. Link it here, then re-run: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT"

step "3/8 Enabling APIs (takes a minute the first time)"
gcloud services enable run.googleapis.com firestore.googleapis.com aiplatform.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com iamcredentials.googleapis.com identitytoolkit.googleapis.com firebase.googleapis.com \
  firebasehosting.googleapis.com compute.googleapis.com

step "4/8 Adding Firebase and a Hosting site"
if ! "${FB[@]}" projects:list --json 2>/dev/null | json "any(p['projectId']=='$PROJECT' for p in d.get('result', []))" | grep -q True; then
  "${FB[@]}" projects:addfirebase "$PROJECT"
fi
if ! "${FB[@]}" hosting:sites:list --project "$PROJECT" --json 2>/dev/null \
     | json "any(s['name'].endswith('/sites/$PROJECT') for s in d.get('result', {}).get('sites', []))" | grep -q True; then
  "${FB[@]}" hosting:sites:create "$PROJECT" --project "$PROJECT" \
    || die "Could not create Hosting site '$PROJECT' (the ID may be taken). Create it in the Firebase console → Hosting."
fi

step "5/8 Registering the Firebase web app and writing .env.deploy"
APP_ID=$("${FB[@]}" apps:list WEB --project "$PROJECT" --json 2>/dev/null | json "next((a['appId'] for a in d.get('result', [])), '')")
if [ -z "$APP_ID" ]; then
  APP_ID=$("${FB[@]}" apps:create WEB KasFlow --project "$PROJECT" --json | json "d['result']['appId']")
fi
SDK=$("${FB[@]}" apps:sdkconfig WEB "$APP_ID" --project "$PROJECT" --json)
cfg() { printf '%s' "$SDK" | json "(d['result'].get('sdkConfig') or json.loads(d['result']['fileContents'][d['result']['fileContents'].index('{'):d['result']['fileContents'].rindex('}')+1]))['$1']"; }
if [ -f .env.deploy ]; then set -a; source .env.deploy; set +a; fi
cat > .env.deploy <<EOF
GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-us-central1}
GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash}
DEMO_CLIENT_API_KEY=${DEMO_CLIENT_API_KEY:-$(openssl rand -hex 16)}
DEMO_LOGIN_KEY=${DEMO_LOGIN_KEY:-$(openssl rand -hex 16)}
FIREBASE_WEB_API_KEY=$(cfg apiKey)
FIREBASE_WEB_AUTH_DOMAIN=$(cfg authDomain)
FIREBASE_WEB_PROJECT_ID=$(cfg projectId)
FIREBASE_WEB_APP_ID=$(cfg appId)
EOF
chmod 600 .env.deploy
echo "Wrote .env.deploy (gitignored). Existing demo keys were kept."

step "6/8 Letting Cloud Build deploy from source"
PNUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
BUILD_SA="${PNUM}-compute@developer.gserviceaccount.com"
for i in 1 2 3 4 5 6; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$BUILD_SA" --role=roles/run.builder \
    --condition=None >/dev/null 2>&1 && break
  [ "$i" = 6 ] && die "Could not grant roles/run.builder to $BUILD_SA"
  sleep 10  # the default compute service account appears shortly after the Compute API is enabled
done

step "7/8 Google sign-in (the one manual click)"
idp_enabled() {
  curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: $PROJECT" \
    "https://identitytoolkit.googleapis.com/admin/v2/projects/$PROJECT/defaultSupportedIdpConfigs/google.com" \
    | json "d.get('enabled') is True" 2>/dev/null | grep -q True
}
until idp_enabled; do
  echo "Open: https://console.firebase.google.com/project/$PROJECT/authentication/providers"
  echo "  Get started (if shown) → Google → Enable → choose a support email → Save"
  read -r -p "Press Enter once it's saved... " _
done
echo "Google sign-in is enabled. <project>.web.app and <project>.firebaseapp.com are authorized automatically."

step "8/8 Checking Gemini on Vertex, then deploying"
set -a; source .env.deploy; set +a
if ! GOOGLE_CLOUD_PROJECT="$PROJECT" "$PY" scripts/check_gemini.py; then
  echo "Gemini check reported problems (see above). A different GEMINI_MODEL in .env.deploy usually fixes model errors."
  read -r -p "Deploy anyway? [y/N] " ans
  [ "$ans" = "y" ] || [ "$ans" = "Y" ] || die "Stopped before deploy. Fix .env.deploy and re-run ./bootstrap.sh $PROJECT $REGION"
fi
./deploy.sh "$PROJECT" "$REGION"

echo
echo "Done. Demo client: https://$PROJECT.web.app/demo/client · Console: https://$PROJECT.web.app/"
echo "Demo login for the video: https://$PROJECT.web.app/demo-login?key=$DEMO_LOGIN_KEY (keep this private)"
