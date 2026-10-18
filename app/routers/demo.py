from decimal import Decimal
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app import seeding
from app.deps import Services, get_services
from app.errors import AppError
from app.models import new_id

router = APIRouter(prefix="/api/demo", include_in_schema=False)


class DemoApply(BaseModel):
    persona: Literal["sari", "paolo", "linh"]
    purpose: str = Field(default="loan", min_length=1, max_length=40)
    requested_amount: Decimal | None = None
    tenor_months: int | None = None


def _internal_client(request: Request) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app), base_url="http://kasflow.internal",
                             timeout=120)


@router.get("/personas")
def personas():
    return {"items": seeding.persona_cards()}


@router.post("/client/apply")
async def apply(body: DemoApply, request: Request, s: Services = Depends(get_services)):
    profile = seeding.load_profile(body.persona)
    payload = {
        "external_ref": f"PC-{new_id()[:8].upper()}", "customer": profile["customer"], "purpose": body.purpose,
        "requested_amount": str(body.requested_amount) if body.requested_amount else None,
        "tenor_months": body.tenor_months, "consent": {"ref": profile["consent_ref"]},
    }
    async with _internal_client(request) as c:
        r = await c.post("/api/v1/assessments", json=payload, headers={"X-API-Key": s.settings.demo_client_api_key})
    return {"request": {"method": "POST", "path": "/api/v1/assessments", "body": payload},
            "response": {"status": r.status_code, "body": r.json()}}


@router.get("/assessment/{assessment_id}")
async def poll(assessment_id: str, request: Request, s: Services = Depends(get_services)):
    path = f"/api/v1/assessments/{assessment_id}"
    async with _internal_client(request) as c:
        r = await c.get(path, headers={"X-API-Key": s.settings.demo_client_api_key})
    return {"request": {"method": "GET", "path": path, "body": None},
            "response": {"status": r.status_code, "body": r.json()}}


@router.get("/custom-token")
def custom_token(key: str = "", s: Services = Depends(get_services)):
    if not key or key != s.settings.demo_login_key:
        raise AppError(403, "forbidden", "Invalid demo key")
    return s.verifier.mint_demo()
