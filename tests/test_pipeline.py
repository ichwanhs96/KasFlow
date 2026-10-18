import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.config import MAX_FILE_BYTES, MAX_ITEMS, Settings
from app.errors import AppError
from app.models import Analyst, CreateAssessmentRequest, PushSourceRequest, ReviewRequest
from app.repo import InMemoryRepo
from app.services import scoring
from app.services.gemini import GeminiError, StubGemini
from app.services.pipeline import AssessmentService

NOW = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
SIX = [(2026, m) for m in range(4, 10)]
THREE = [(2026, m) for m in range(7, 10)]


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


def provider_account(months, per_month):
    txns, bal, i = [], 1_000_000, 0
    for (y, m) in months:
        for k in range(per_month):
            amt = 100_000 + k * 1_000
            bal += amt
            i += 1
            txns.append({"txn_id": f"t{i}", "posted": date(y, m, 2 + k).strftime("%d/%m/%Y"), "amt": f"{amt}.00",
                         "cr_dr": "CR", "narrative": "SALES", "category": "SALES", "running_bal": f"{bal}.00",
                         "counterparty_name": None})
        bal -= 50_000
        i += 1
        txns.append({"txn_id": f"t{i}", "posted": date(y, m, 27).strftime("%d/%m/%Y"), "amt": "50000.00",
                     "cr_dr": "DR", "narrative": "SUPPLIER", "category": "OTHER", "running_bal": f"{bal}.00",
                     "counterparty_name": None})
    return {"account_id": "a1", "institution": "Bank T", "type": "bank", "currency": "IDR", "masked_number": "••1",
            "transactions": txns}


def csv_bytes():
    lines = ["Tgl;Nominal;Ket"]
    for (y, m) in SIX:
        for k in range(4):
            amt = 1_500_000 + k * 10_000
            lines.append(f"{date(y, m, 10 + k).strftime('%d-%m-%Y')};{amt:,};QRIS".replace(",", "."))
    return ("\n".join(lines) + "\n").encode()


@pytest.fixture
def env(tmp_path):
    data = tmp_path / "personas"
    fx = data / "extracted"
    fx.mkdir(parents=True)
    for name, months, per in (("sari", THREE, 2), ("paolo", SIX, 4)):
        (data / f"{name}_open_finance.json").write_text(json.dumps(
            {"provider": "openfinance-sea-sim", "consent_ref": f"of-{name}-001",
             "accounts": [provider_account(months, per)]}))
    rows = [{"date": date(y, m, 3 + k).isoformat(), "description": "QR sale", "amount": 20000 + k * 100,
             "direction": "in", "balance": None, "counterparty": None, "kind": "normal"} for (y, m) in SIX for k in range(4)]
    (fx / "wallet.png.json").write_text(json.dumps(
        {"document_type": "ewallet_history", "channel": "ewallet", "institution": "W", "currency": "IDR", "rows": rows}))
    (fx / "stmt.csv.mapping.json").write_text(json.dumps(
        {"date_column": "Tgl", "date_format": "%d-%m-%Y", "amount_column": "Nominal", "debit_column": None,
         "credit_column": None, "direction_column": None, "direction_in_values": [], "description_column": "Ket",
         "balance_column": None, "counterparty_column": None, "thousands_separator": ".", "decimal_separator": ",",
         "channel": "qris", "status_column": None, "success_values": []}))
    clock = Clock()
    repo = InMemoryRepo()
    svc = AssessmentService(repo, StubGemini(fx), Settings(public_base_url="https://kf.test"), clock=clock, data_dir=data)
    return svc, repo, clock


def req(ref="of-sari-001", **kw):
    return CreateAssessmentRequest(
        customer={"name": "Sari W", "type": "business", "occupation_or_business_type": "Warung", "country": "ID",
                  "years_active": 5}, purpose="loan", consent={"ref": ref}, **kw)


def token_of(url):
    return url.rsplit("/c/", 1)[1]


def upload_csv(svc, t):
    return svc.add_item(t, data=csv_bytes(), filename="stmt.csv", mime_type="text/csv", kind="upload")


def test_create_thin_needs_more_data(env):
    svc, _, _ = env
    a, url = svc.create("c1", req())
    assert a.status == "needs_more_data" and url.startswith("https://kf.test/c/")
    assert a.collection is not None and a.sufficiency.months_covered == 3
    assert [e.type for e in a.events][:3] == ["created", "open_finance_fetched", "collection_link_issued"]
    assert a.sources[0].trust == "verified" and a.sources[0].kind == "open_finance"
    assert a.currency == "IDR" and a.consent.expires_at == NOW + timedelta(days=30)


def test_create_sufficient_scores_with_summary(env):
    svc, _, _ = env
    a, url = svc.create("c1", req("of-paolo-001"))
    assert url is None and a.status == "scored" and a.result.ai_summary is not None and a.collection is None


def test_unknown_ref_then_score_now_handles_no_data(env):
    svc, _, _ = env
    a, _ = svc.create("c1", req("of-unknown"))
    assert a.status == "needs_more_data" and a.sources == []
    a = svc.score_now(a.id, "analyst:x@y.z")
    assert a.status == "scored" and a.result.limited_data
    assert a.result.grade == "D" and a.result.recommendation == "unfavorable"


def test_upload_then_complete_scores(env):
    svc, repo, _ = env
    a, url = svc.create("c1", req())
    t = token_of(url)
    item = upload_csv(svc, t)
    assert item.status == "done" and item.txn_count == 24
    mid = repo.get_assessment(a.id)
    assert mid.status == "needs_more_data" and mid.sufficiency.sufficient
    done = svc.complete(t)
    assert done.status == "scored" and not done.result.limited_data
    assert any(s.kind == "upload" and s.trust == "extracted" for s in done.sources)
    assert "collection_completed" in [e.type for e in done.events]


def test_same_file_twice_counts_once(env):
    svc, _, _ = env

    def flow(times):
        _, url = svc.create("c1", req())
        t = token_of(url)
        for _ in range(times):
            upload_csv(svc, t)
        return svc.complete(t)

    assert flow(2).result.metrics.avg_monthly_inflow == flow(1).result.metrics.avg_monthly_inflow


def test_unreadable_photo_marks_item_failed(env):
    svc, repo, _ = env
    a, url = svc.create("c1", req())
    t = token_of(url)
    item = svc.add_item(t, data=b"\xff\xd8not-a-statement", filename="cat.jpg", mime_type="image/jpeg", kind="camera")
    assert item.status == "failed" and item.error == "extract_failed"
    stored = repo.get_assessment(a.id)
    assert stored.status == "needs_more_data" and len(stored.sources) == 1
    assert stored.collection.items[0].status == "failed"
    with pytest.raises(AppError) as e:
        svc.complete(t)
    assert e.value.code == "no_items"


def test_camera_photo_creates_camera_source(env):
    svc, repo, _ = env
    a, url = svc.create("c1", req())
    item = svc.add_item(token_of(url), data=b"img", filename="wallet.png", mime_type="image/png", kind="camera")
    assert item.status == "done"
    assert repo.get_assessment(a.id).sources[-1].kind == "camera"


def test_token_states(env):
    svc, _, clock = env
    with pytest.raises(AppError) as e:
        svc.resolve_token("nope")
    assert e.value.status == 404 and e.value.code == "invalid_link"
    _, url = svc.create("c1", req())
    t = token_of(url)
    clock.now = NOW + timedelta(hours=73)
    with pytest.raises(AppError) as e:
        svc.resolve_token(t)
    assert e.value.status == 410
    clock.now = NOW
    upload_csv(svc, t)
    svc.complete(t)
    with pytest.raises(AppError) as e:
        svc.resolve_token(t)
    assert e.value.status == 409


def test_upload_validation(env):
    svc, _, _ = env
    _, url = svc.create("c1", req())
    t = token_of(url)
    for data, name, mime, code in ((b"x", "a.gif", "image/gif", "unsupported_file"),
                                   (b"", "a.pdf", "application/pdf", "empty_file"),
                                   (b"x" * (MAX_FILE_BYTES + 1), "a.pdf", "application/pdf", "file_too_large")):
        with pytest.raises(AppError) as e:
            svc.add_item(t, data=data, filename=name, mime_type=mime, kind="upload")
        assert e.value.status == 422 and e.value.code == code
    for _ in range(MAX_ITEMS):
        svc.add_item(t, data=b"x", filename="cat.jpg", mime_type="image/jpeg", kind="upload")
    with pytest.raises(AppError) as e:
        svc.add_item(t, data=b"x", filename="cat.jpg", mime_type="image/jpeg", kind="upload")
    assert e.value.code == "too_many_items"


def test_csv_accepted_by_extension(env):
    svc, _, _ = env
    _, url = svc.create("c1", req())
    item = svc.add_item(token_of(url), data=csv_bytes(), filename="stmt.csv", mime_type="application/octet-stream",
                        kind="upload")
    assert item.status == "done" and item.mime_type == "text/csv"


def test_push_sources(env):
    svc, _, _ = env
    a, _ = svc.create("c1", req())
    _, s1, _ = svc.push_source("c1", a.id, PushSourceRequest(
        label="Core", format="standard", transactions=[{"date": "2026-09-01", "amount": "1000", "direction": "in"}]))
    assert s1.trust == "verified" and s1.kind == "api_push"
    stub = {"document_type": "other", "channel": "other", "institution": None, "currency": "IDR",
            "rows": [{"date": "2026-09-02", "description": "x", "amount": 500, "direction": "in", "balance": None,
                      "counterparty": None, "kind": "normal"}]}
    _, s2, _ = svc.push_source("c1", a.id, PushSourceRequest(label="Auto", format="auto",
                                                             payload={"__stub_extraction__": stub}))
    assert s2.trust == "extracted"
    with pytest.raises(AppError) as e:
        svc.push_source("c1", a.id, PushSourceRequest(label="Bad", format="auto", payload={"x": 1}))
    assert e.value.code == "unmappable_payload"
    with pytest.raises(AppError) as e:
        svc.push_source("someone-else", a.id, PushSourceRequest(label="Bad", format="auto", payload={"x": 1}))
    assert e.value.status == 404


def test_review(env):
    svc, _, _ = env
    analyst = Analyst(uid="u", email="x@y.z")
    a, _ = svc.create("c1", req("of-paolo-001"))
    r = svc.review(a.id, analyst, ReviewRequest(action="override", final_recommendation="unfavorable", note="n"))
    assert r.status == "reviewed" and r.review.final_recommendation == "unfavorable" and r.review.analyst_email == "x@y.z"
    accepted = svc.review(a.id, analyst, ReviewRequest(action="accept"))
    assert accepted.review.final_recommendation == accepted.result.recommendation
    b, _ = svc.create("c1", req())
    with pytest.raises(AppError) as e:
        svc.review(b.id, analyst, ReviewRequest(action="accept"))
    assert e.value.status == 409


def test_summary_failure_keeps_score_and_regenerates(env):
    svc, _, _ = env
    good = svc.gemini

    class Failing(StubGemini):
        def summarize(self, facts, *, purpose, language):
            raise GeminiError("boom")

    svc.gemini = Failing(good.fixtures_dir)
    a, _ = svc.create("c1", req("of-paolo-001"))
    assert a.status == "scored" and a.result.ai_summary is None and "summary_failed" in [e.type for e in a.events]
    svc.gemini = good
    assert svc.regenerate_summary(a.id, "analyst:x").result.ai_summary is not None


def test_pipeline_crash_sets_error(env, monkeypatch):
    svc, repo, _ = env

    def boom(*a, **k):
        raise RuntimeError("kaput")

    monkeypatch.setattr(scoring, "score", boom)
    with pytest.raises(AppError) as e:
        svc.create("c1", req("of-paolo-001"))
    assert e.value.status == 500
    stored = repo.list_assessments()[0]
    assert stored.status == "error" and "kaput" in stored.error


def test_list_filters_and_sorts(env):
    svc, _, clock = env
    a, _ = svc.create("c1", req())
    clock.now = NOW + timedelta(minutes=1)
    b, _ = svc.create("c1", req("of-paolo-001"))
    assert [x.id for x in svc.list()][0] in (a.id, b.id)
    assert [x.id for x in svc.list("scored")] == [b.id]
