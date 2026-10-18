from app.services.tokens import hash_secret

KEY = {"X-API-Key": "dev-client-key"}
CUSTOMER = {"name": "Sari Wulandari", "type": "business", "occupation_or_business_type": "Warung", "country": "ID",
            "years_active": 6}
SARI = {"customer": CUSTOMER, "purpose": "loan", "requested_amount": 50000000, "tenor_months": 12,
        "consent": {"ref": "of-sari-001"}}
PAOLO = {"customer": {"name": "Paolo Reyes", "type": "individual", "occupation_or_business_type": "Driver",
                      "country": "PH", "years_active": 3},
         "purpose": "loan", "requested_amount": 80000, "tenor_months": 6, "consent": {"ref": "of-paolo-001"}}


def test_health_and_config(client):
    assert client.get("/healthz").json() == {"ok": True}
    assert '"authMode": "stub"' in client.get("/config.js").text


def test_requires_api_key(client):
    r = client.post("/api/v1/assessments", json=SARI)
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
    r = client.post("/api/v1/assessments", json=SARI, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_create_thin_returns_collection_url(client):
    r = client.post("/api/v1/assessments", json=SARI, headers=KEY)
    body = r.json()
    assert r.status_code == 201 and body["status"] == "needs_more_data"
    assert body["collection_url"].startswith("http://localhost:8080/c/") and body["result"] is None
    assert body["sufficiency"]["months_covered"] == 3 and body["collection_expires_at"]


def test_create_full_is_scored(client):
    body = client.post("/api/v1/assessments", json=PAOLO, headers=KEY).json()
    assert body["status"] == "scored" and body["collection_url"] is None
    assert body["result"]["grade"] == "C" and body["result"]["recommendation"] == "review"
    assert body["result"]["customer_explanation_local"]


def test_get_and_client_isolation(client, services):
    created = client.post("/api/v1/assessments", json=SARI, headers=KEY).json()
    got = client.get(f"/api/v1/assessments/{created['id']}", headers=KEY).json()
    assert got["id"] == created["id"] and got["collection_url"] is None and got["status"] == "needs_more_data"
    services.repo.put_client("other", {"name": "Other", "api_key_hash": hash_secret("other-key")})
    r = client.get(f"/api/v1/assessments/{created['id']}", headers={"X-API-Key": "other-key"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_validation_error_format(client):
    r = client.post("/api/v1/assessments", json={"purpose": "loan"}, headers=KEY)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_push_standard_source(client):
    a = client.post("/api/v1/assessments", json=SARI, headers=KEY).json()
    r = client.post(f"/api/v1/assessments/{a['id']}/sources", headers=KEY, json={
        "label": "Core banking export", "format": "standard",
        "transactions": [{"date": "2026-09-01", "amount": "150000", "direction": "in", "channel": "bank"}]})
    body = r.json()
    assert r.status_code == 201 and body["txn_count"] == 1 and body["source_id"]
    assert any(s["kind"] == "api_push" and s["trust"] == "verified" for s in body["sources"])


def test_collection_link_reissue(client):
    a = client.post("/api/v1/assessments", json=SARI, headers=KEY).json()
    r = client.post(f"/api/v1/assessments/{a['id']}/collection-link", headers=KEY).json()
    assert r["collection_url"] != a["collection_url"] and r["collection_expires_at"]


def test_openapi_documents_only_client_routes(client):
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "KasFlow Client API"
    assert spec["paths"] and all(p.startswith("/api/v1/") for p in spec["paths"])
    assert client.get("/docs").status_code == 200
