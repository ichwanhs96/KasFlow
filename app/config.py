from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "personas"
ASSETS_DIR = ROOT / "demo_assets"
STATIC_DIR = ROOT / "app" / "static"

ANNUAL_RATE = Decimal("0.18")
COVERAGE_TARGET = Decimal("1.5")
MIN_MONTHS = 6
MIN_INFLOW_TXNS = 20
COLLECTION_TTL_HOURS = 72
CONSENT_TTL_DAYS = 30
MAX_ITEMS = 8
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TXNS = 2000
GEMINI_TIMEOUT_S = 45
JSON_PAYLOAD_MAX_BYTES = 200_000
DEMO_CLIENT_ID = "pinjamcepat"
DEMO_ANALYST_EMAIL = "demo-analyst@kasflow.demo"


@dataclass(frozen=True)
class Settings:
    project: str = ""
    location: str = "us-central1"
    gemini_model: str = "gemini-2.5-flash"
    demo_client_api_key: str = "dev-client-key"
    demo_login_key: str = "dev-login-key"
    public_base_url: str = "http://localhost:8080"
    firebase_web: dict = field(default_factory=dict)
    repo_backend: str = "memory"
    gemini_backend: str = "stub"
    auth_backend: str = "stub"
    seed_on_start: bool = False


def load_settings() -> Settings:
    e = os.environ.get
    return Settings(
        project=e("GOOGLE_CLOUD_PROJECT", ""),
        location=e("GOOGLE_CLOUD_LOCATION", "us-central1"),
        gemini_model=e("GEMINI_MODEL", "gemini-2.5-flash"),
        demo_client_api_key=e("DEMO_CLIENT_API_KEY", "dev-client-key"),
        demo_login_key=e("DEMO_LOGIN_KEY", "dev-login-key"),
        public_base_url=e("PUBLIC_BASE_URL", "http://localhost:8080"),
        firebase_web={
            "apiKey": e("FIREBASE_WEB_API_KEY", ""),
            "authDomain": e("FIREBASE_WEB_AUTH_DOMAIN", ""),
            "projectId": e("FIREBASE_WEB_PROJECT_ID", ""),
            "appId": e("FIREBASE_WEB_APP_ID", ""),
        },
        repo_backend=e("REPO_BACKEND", "memory"),
        gemini_backend=e("GEMINI_BACKEND", "stub"),
        auth_backend=e("AUTH_BACKEND", "stub"),
        seed_on_start=e("SEED_ON_START", "false").lower() == "true",
    )
