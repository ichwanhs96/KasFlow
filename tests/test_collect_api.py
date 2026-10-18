from datetime import timedelta

from app import seeding
from app.config import ASSETS_DIR


def new_link(services):
    _, url = services.assessments.create("pinjamcepat", seeding.build_request(seeding.load_profile("sari"), "T-C"))
    return url.rsplit("/c/", 1)[1]


def test_collect_info_and_invalid(client, services):
    t = new_link(services)
    info = client.get(f"/api/collect/{t}").json()
    assert info["client_name"] == "PinjamCepat" and info["language"] == "id" and info["customer_first_name"] == "Sari"
    r = client.get("/api/collect/not-a-token")
    assert r.status_code == 404 and r.json()["error"]["code"] == "invalid_link"


def test_collect_upload_and_complete(client, services):
    t = new_link(services)
    with open(ASSETS_DIR / "sari_qris.csv", "rb") as f:
        r = client.post(f"/api/collect/{t}/items", files={"file": ("sari_qris.csv", f, "text/csv")},
                        data={"kind": "upload"})
    assert r.status_code == 200 and r.json()["status"] == "done" and r.json()["txn_count"] > 100
    assert client.post(f"/api/collect/{t}/complete").json() == {"status": "received"}
    again = client.get(f"/api/collect/{t}")
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_completed"


def test_collect_unreadable_file_returns_failed_200(client, services):
    t = new_link(services)
    r = client.post(f"/api/collect/{t}/items", files={"file": ("cat.jpg", b"\xff\xd8\xff", "image/jpeg")},
                    data={"kind": "camera"})
    assert r.status_code == 200 and r.json() == {"item_id": r.json()["item_id"], "status": "failed",
                                                  "message_key": "extract_failed"}
    assert client.post(f"/api/collect/{t}/complete").status_code == 422


def test_collect_rejects_bad_type_and_expired(client, services, clock):
    t = new_link(services)
    r = client.post(f"/api/collect/{t}/items", files={"file": ("a.gif", b"GIF89a", "image/gif")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unsupported_file"
    clock.now = clock.now + timedelta(hours=73)
    assert client.get(f"/api/collect/{t}").status_code == 410
