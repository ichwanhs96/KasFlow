#!/usr/bin/env python3
"""Smoke-test a running KasFlow (local or deployed). Usage: smoke.py <BASE_URL>. Env: DEMO_CLIENT_API_KEY."""
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import seeding  # noqa: E402


def main() -> int:
    base = sys.argv[1].rstrip("/")
    key = os.environ.get("DEMO_CLIENT_API_KEY", "dev-client-key")
    with httpx.Client(base_url=base, timeout=120) as c:
        assert c.get("/healthz").json() == {"ok": True}, "healthz failed"
        req = seeding.build_request(seeding.load_profile("paolo"), "SMOKE-PAOLO").model_dump(mode="json")
        r = c.post("/api/v1/assessments", json=req, headers={"X-API-Key": key})
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "scored", r.text
        assert c.get("/docs").status_code == 200, "docs failed"
        assert c.get("/demo/client").status_code == 200, "demo client failed"
    print(f"SMOKE OK: {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
