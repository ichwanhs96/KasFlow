def test_index_and_console_pages(client):
    r = client.get("/")
    assert r.status_code == 200 and "Sign in with Google" in r.text and "/static/js/firebase.js" in r.text
    c = client.get("/console")
    assert c.status_code == 200 and 'x-data="consoleApp"' in c.text
    for testid in ("assessment-row", "source-card", "metric-chip", "review-submit", "tampered-row"):
        assert testid in c.text
    assert client.get("/static/js/console.js").status_code == 200
    assert client.get("/static/js/firebase.js").status_code == 200


def test_collect_page_is_embeddable(client):
    r = client.get("/c/some-token")
    assert r.status_code == 200 and 'x-data="collectApp"' in r.text
    assert r.headers["content-security-policy"] == "frame-ancestors *"
    assert "x-frame-options" not in {k.lower() for k in r.headers}
    for testid in ("file-input", "take-photo", "capture", "done", "collect-item"):
        assert testid in r.text
    js = client.get("/static/js/i18n.js").text
    for s in ("Ambil foto", "transaksi terbaca", "Selesai", "Kumuha ng litrato", "Chụp ảnh"):
        assert s in js
