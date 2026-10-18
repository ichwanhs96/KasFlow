import json
from datetime import datetime
from pathlib import Path

PROVIDER = "openfinance-sea-sim"
REF_TO_PERSONA = {"of-sari-001": "sari", "of-paolo-001": "paolo", "of-linh-001": "linh"}


def fetch(consent_ref: str, *, data_dir: Path, now: datetime) -> dict:
    persona = REF_TO_PERSONA.get(consent_ref)
    path = data_dir / f"{persona}_open_finance.json" if persona else None
    if not path or not path.exists():
        return {"provider": PROVIDER, "consent_ref": consent_ref, "fetched_at": now.isoformat(), "accounts": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["fetched_at"] = now.isoformat()
    return payload
