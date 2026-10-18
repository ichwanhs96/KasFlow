def test_personas(client):
    items = client.get("/api/demo/personas").json()["items"]
    assert [p["id"] for p in items] == ["sari", "paolo", "linh"]
    assert items[0]["accounts"][0]["institution"] == "Bank Merapi"


def test_apply_uses_real_client_api(client):
    r = client.post("/api/demo/client/apply", json={"persona": "sari", "purpose": "loan",
                                                    "requested_amount": 50000000, "tenor_months": 12}).json()
    assert r["request"]["method"] == "POST" and r["request"]["path"] == "/api/v1/assessments"
    assert r["request"]["body"]["consent"]["ref"] == "of-sari-001"
    assert r["response"]["status"] == 201 and r["response"]["body"]["status"] == "needs_more_data"
    poll = client.get(f"/api/demo/assessment/{r['response']['body']['id']}").json()
    assert poll["response"]["status"] == 200 and poll["request"]["method"] == "GET"


def test_custom_token(client):
    assert client.get("/api/demo/custom-token?key=wrong").status_code == 403
    assert client.get("/api/demo/custom-token?key=dev-login-key").json() == {
        "mode": "stub", "token": "stub:demo-analyst@kasflow.demo"}
