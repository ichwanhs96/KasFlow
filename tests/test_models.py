import pytest
from pydantic import ValidationError

from app.models import (
    CreateAssessmentRequest, Customer, PushSourceRequest, ReviewRequest, Transaction, new_id,
)


def test_transaction_amount_must_be_positive():
    with pytest.raises(ValidationError):
        Transaction(id=new_id(), date="2026-09-01", amount="0", direction="in", currency="IDR",
                    source_id="s", row_index=0)


def test_customer_country_is_restricted():
    with pytest.raises(ValidationError):
        Customer(name="A", type="business", occupation_or_business_type="Shop", country="SG", years_active=1)


def test_push_source_requires_matching_body():
    with pytest.raises(ValidationError):
        PushSourceRequest(label="x", format="standard", transactions=[])
    with pytest.raises(ValidationError):
        PushSourceRequest(label="x", format="auto")
    assert PushSourceRequest(label="x", format="auto", payload={"a": 1}).payload == {"a": 1}


def test_review_override_requires_final_recommendation():
    with pytest.raises(ValidationError):
        ReviewRequest(action="override")
    assert ReviewRequest(action="accept").final_recommendation is None


def test_create_request_parses_nested():
    r = CreateAssessmentRequest(
        customer={"name": "Sari", "type": "business", "occupation_or_business_type": "Warung",
                  "country": "ID", "years_active": 6},
        purpose="loan", requested_amount=50000000, tenor_months=12, consent={"ref": "of-sari-001"})
    assert r.consent.provider == "openfinance-sea-sim"


def test_health_and_config(client):
    assert client.get("/healthz").json() == {"ok": True}
    r = client.get("/config.js")
    assert r.status_code == 200 and '"authMode": "stub"' in r.text
