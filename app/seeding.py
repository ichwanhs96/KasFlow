from __future__ import annotations

import json
from pathlib import Path

from app.config import ASSETS_DIR, DATA_DIR, DEMO_CLIENT_ID, Settings
from app.i18n import currency_for
from app.models import Assessment, CreateAssessmentRequest, utcnow
from app.services.tokens import hash_secret

PERSONAS = ("sari", "paolo", "linh")
UPLOADS: dict[str, list[tuple[str, str, str]]] = {
    "sari": [("sari_dompetku.png", "image/png", "upload"), ("sari_qris.csv", "text/csv", "upload"),
             ("sari_buku_kas.png", "image/png", "camera")],
    "paolo": [],
    "linh": [("linh_statement.pdf", "application/pdf", "upload")],
}


def load_profile(persona: str, data_dir: Path = DATA_DIR) -> dict:
    return json.loads((Path(data_dir) / f"{persona}_profile.json").read_text(encoding="utf-8"))


def build_request(profile: dict, external_ref: str) -> CreateAssessmentRequest:
    return CreateAssessmentRequest(
        external_ref=external_ref, customer=profile["customer"], purpose=profile["purpose"],
        requested_amount=profile.get("requested_amount"), tenor_months=profile.get("tenor_months"),
        consent={"ref": profile["consent_ref"]})


def persona_cards(data_dir: Path = DATA_DIR) -> list[dict]:
    cards = []
    for p in PERSONAS:
        prof = load_profile(p, data_dir)
        of = json.loads((Path(data_dir) / f"{p}_open_finance.json").read_text(encoding="utf-8"))
        cards.append({
            "id": p, "label": prof["label"], "customer": prof["customer"], "purpose": prof["purpose"],
            "requested_amount": prof.get("requested_amount"), "tenor_months": prof.get("tenor_months"),
            "currency": currency_for(prof["customer"]["country"]),
            "accounts": [{"institution": a["institution"], "masked_number": a["masked_number"], "type": a["type"]}
                         for a in of["accounts"]],
        })
    return cards


def ensure_demo_client(repo, settings: Settings) -> None:
    repo.put_client(DEMO_CLIENT_ID, {"name": "PinjamCepat", "api_key_hash": hash_secret(settings.demo_client_api_key),
                                     "created_at": utcnow().isoformat()})


def run_persona(service, persona: str, *, external_ref: str, client_id: str = DEMO_CLIENT_ID,
                assets_dir: Path = ASSETS_DIR, data_dir: Path = DATA_DIR) -> Assessment:
    a, url = service.create(client_id, build_request(load_profile(persona, data_dir), external_ref))
    if url and UPLOADS[persona]:
        token = url.rsplit("/c/", 1)[1]
        for filename, mime, kind in UPLOADS[persona]:
            service.add_item(token, data=(Path(assets_dir) / filename).read_bytes(), filename=filename,
                             mime_type=mime, kind=kind)
        a = service.complete(token)
    return a


def seed(repo, service, settings: Settings, personas=("paolo", "linh")) -> list[Assessment]:
    ensure_demo_client(repo, settings)
    for a in repo.list_assessments(DEMO_CLIENT_ID):
        if (a.external_ref or "").startswith("SEED-"):
            repo.delete_assessment(a.id)
    return [run_persona(service, p, external_ref=f"SEED-{p.upper()}") for p in personas]
