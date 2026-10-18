import firebase_admin.auth
import pytest

from app import seeding
from app.auth import FirebaseVerifier
from app.errors import AppError

AUTH = {"Authorization": "Bearer stub:analyst@test.dev"}


def make(services, persona):
    return seeding.run_persona(services.assessments, persona, external_ref=f"T-{persona}")


def test_console_requires_auth(client):
    assert client.get("/api/console/assessments").status_code == 401
    assert client.get("/api/console/assessments", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/console/me", headers=AUTH).json()["email"] == "analyst@test.dev"


def test_list_detail_and_transactions(client, services):
    linh = make(services, "linh")
    make(services, "paolo")
    items = client.get("/api/console/assessments", headers=AUTH).json()["items"]
    assert {i["customer"]["name"] for i in items} >= {"Nguyễn Thị Linh", "Paolo Reyes"}
    assert all(i["status"] == "scored" for i in client.get("/api/console/assessments?status=scored",
                                                            headers=AUTH).json()["items"])
    detail = client.get(f"/api/console/assessments/{linh.id}", headers=AUTH).json()
    assert detail["result"]["grade"] == "D" and len(detail["sources"]) == 2
    txns = client.get(f"/api/console/assessments/{linh.id}/transactions", headers=AUTH).json()["items"]
    assert sum(1 for t in txns if t["tampered"]) == 2


def test_collection_link_score_now_summary_and_review(client, services):
    a, _ = services.assessments.create("pinjamcepat", seeding.build_request(seeding.load_profile("sari"), "T-S"))
    link = client.post(f"/api/console/assessments/{a.id}/collection-link", headers=AUTH).json()
    assert link["collection_url"].startswith("http://localhost:8080/c/") and "<svg" in link["qr_svg"]
    scored = client.post(f"/api/console/assessments/{a.id}/score", headers=AUTH).json()
    assert scored["status"] == "scored" and scored["result"]["limited_data"] is True
    assert client.post(f"/api/console/assessments/{a.id}/summary", headers=AUTH).json()["result"]["ai_summary"]
    bad = client.post(f"/api/console/assessments/{a.id}/review", headers=AUTH, json={"action": "override"})
    assert bad.status_code == 422
    ok = client.post(f"/api/console/assessments/{a.id}/review", headers=AUTH,
                     json={"action": "override", "final_recommendation": "favorable", "note": "Known customer"}).json()
    assert ok["status"] == "reviewed" and ok["review"]["analyst_email"] == "analyst@test.dev"


def test_firebase_verifier_provider_check(monkeypatch):
    v = FirebaseVerifier("demo-project")
    monkeypatch.setattr(firebase_admin.auth, "verify_id_token",
                        lambda t: {"uid": "u1", "email": "a@b.c", "firebase": {"sign_in_provider": "google.com"}})
    assert v.verify("t").email == "a@b.c"
    monkeypatch.setattr(firebase_admin.auth, "verify_id_token",
                        lambda t: {"uid": "u1", "firebase": {"sign_in_provider": "password"}})
    with pytest.raises(AppError) as e:
        v.verify("t")
    assert e.value.status == 403

    def boom(t):
        raise ValueError("bad")

    monkeypatch.setattr(firebase_admin.auth, "verify_id_token", boom)
    with pytest.raises(AppError) as e:
        v.verify("t")
    assert e.value.status == 401
