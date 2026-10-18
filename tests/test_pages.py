def test_index_and_console_pages(client):
    r = client.get("/")
    assert r.status_code == 200 and "Sign in with Google" in r.text and "/static/js/firebase.js" in r.text
    c = client.get("/console")
    assert c.status_code == 200 and 'x-data="consoleApp"' in c.text
    for testid in ("assessment-row", "source-card", "metric-chip", "review-submit", "tampered-row"):
        assert testid in c.text
    assert client.get("/static/js/console.js").status_code == 200
    assert client.get("/static/js/firebase.js").status_code == 200
