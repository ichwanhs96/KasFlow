#!/usr/bin/env bash
# Phase B only. Usage: ./deploy.sh <PROJECT_ID> [REGION]
# Requires: gcloud auth login, `npx firebase-tools login`, and a filled-in .env.deploy (see ACCESS.md).
set -euo pipefail
PROJECT="${1:?usage: ./deploy.sh <PROJECT_ID> [REGION]}"
REGION="${2:-asia-southeast1}"
[ -f .env.deploy ] || { echo "Create .env.deploy first (see ACCESS.md)"; exit 1; }
set -a; source .env.deploy; set +a
VERTEX_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SA="kasflow-run@${PROJECT}.iam.gserviceaccount.com"
BASE_URL="https://${PROJECT}.web.app"

gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com firestore.googleapis.com aiplatform.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com \
  identitytoolkit.googleapis.com firebase.googleapis.com firebasehosting.googleapis.com

gcloud firestore databases describe --database="(default)" >/dev/null 2>&1 || \
  gcloud firestore databases create --location="$REGION" --type=firestore-native

gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create kasflow-run --display-name="KasFlow Cloud Run"
for ROLE in roles/datastore.user roles/aiplatform.user roles/firebaseauth.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role="$ROLE" --condition=None >/dev/null
done
gcloud iam service-accounts add-iam-policy-binding "$SA" --member="serviceAccount:$SA" \
  --role=roles/iam.serviceAccountTokenCreator >/dev/null

gcloud run deploy kasflow --source . --region "$REGION" --service-account "$SA" --allow-unauthenticated \
  --min-instances 0 --cpu-boost --timeout 300 --memory 1Gi \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=$VERTEX_LOCATION,GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash},PUBLIC_BASE_URL=$BASE_URL,REPO_BACKEND=firestore,GEMINI_BACKEND=vertex,AUTH_BACKEND=firebase,DEMO_CLIENT_API_KEY=$DEMO_CLIENT_API_KEY,DEMO_LOGIN_KEY=$DEMO_LOGIN_KEY,FIREBASE_WEB_API_KEY=$FIREBASE_WEB_API_KEY,FIREBASE_WEB_AUTH_DOMAIN=$FIREBASE_WEB_AUTH_DOMAIN,FIREBASE_WEB_PROJECT_ID=$FIREBASE_WEB_PROJECT_ID,FIREBASE_WEB_APP_ID=$FIREBASE_WEB_APP_ID"

cat > .firebaserc <<EOF
{ "projects": { "default": "$PROJECT" } }
EOF
cat > firebase.json <<EOF
{
  "hosting": {
    "public": "hosting_public",
    "rewrites": [{ "source": "**", "run": { "serviceId": "kasflow", "region": "$REGION" } }]
  },
  "firestore": { "rules": "firestore.rules" }
}
EOF
npx --yes firebase-tools@13 deploy --only hosting,firestore:rules --project "$PROJECT"

GOOGLE_CLOUD_PROJECT="$PROJECT" GOOGLE_CLOUD_LOCATION="$VERTEX_LOCATION" REPO_BACKEND=firestore GEMINI_BACKEND=vertex \
  .venv/bin/python scripts/seed.py
.venv/bin/python scripts/smoke.py "$BASE_URL"
echo "Deployed: $BASE_URL"
