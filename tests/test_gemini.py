import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.models import AiSummary, Extraction, Point
from app.services import prompts
from app.services.gemini import (
    GeminiError, StubGemini, VertexGemini, extraction_to_transactions, stub_summary, validate_summary,
)

REF = date(2026, 10, 18)


def ext(rows, currency="IDR", channel="ewallet"):
    return Extraction(document_type="ewallet_history", channel=channel, institution="W", currency=currency, rows=rows)


def row(d, amount, direction="in", **kw):
    return {"date": d, "description": kw.get("description", " x "), "amount": amount, "direction": direction,
            "balance": kw.get("balance"), "counterparty": kw.get("counterparty"), "kind": kw.get("kind", "normal")}


def test_extraction_post_processing_drops_bad_rows():
    e = ext([row("2026-09-01", 100), row("not-a-date", 5), row("2026-11-01", 5), row("2024-01-01", 5),
             row("2026-09-02", 0), row("2026-09-03", -4), row("2026-09-04", 12.5, "out", counterparty=" Shop ")])
    txns = extraction_to_transactions(e, source_id="s", currency="PHP", reference_date=REF)
    assert [t.amount for t in txns] == [Decimal("100"), Decimal("12.5")]
    assert [t.row_index for t in txns] == [0, 6]
    assert txns[0].description == "x" and txns[1].counterparty == "Shop" and txns[0].channel == "ewallet"
    assert txns[0].currency == "IDR"
    assert extraction_to_transactions(ext([row("2026-09-01", 1)], currency="Rp"), source_id="s", currency="PHP",
                                      reference_date=REF)[0].currency == "PHP"


def test_stub_loads_fixtures_and_camera_fallback(tmp_path):
    (tmp_path / "w.png.json").write_text(ext([row("2026-09-01", 1)]).model_dump_json())
    (tmp_path / "sari_buku_kas.png.json").write_text(ext([row("2026-09-02", 2)], channel="cash").model_dump_json())
    g = StubGemini(tmp_path)
    assert g.extract_document(b"", "image/png", filename="w.png", country="ID", reference_date=REF).rows[0].amount == 1
    assert g.extract_document(b"", "image/jpeg", filename="photo-3.jpg", country="ID",
                              reference_date=REF).channel == "cash"
    with pytest.raises(GeminiError):
        g.extract_document(b"", "image/jpeg", filename="cat.jpg", country="ID", reference_date=REF)
    with pytest.raises(GeminiError):
        g.map_csv_columns(["a"], [["1"]], filename="x.csv", country="ID")
    stub = ext([row("2026-09-01", 1)]).model_dump()
    assert g.map_json({"__stub_extraction__": stub}, country="ID", reference_date=REF).rows[0].amount == 1
    with pytest.raises(GeminiError):
        g.map_json({"a": 1}, country="ID", reference_date=REF)


def _summary(strength_metric="avg_monthly_net", risk_metric="income_cv"):
    return AiSummary(headline="h", summary="s", strengths=[Point(point="p", metric=strength_metric)],
                     risks=[Point(point="r", metric=risk_metric)], data_notes=[], next_steps=[],
                     customer_explanation_local="l", customer_explanation_en="e")


def test_validate_summary_drops_unknown_metrics():
    s = _summary().model_copy(update={"risks": [Point(point="r", metric="income_cv"), Point(point="z", metric="bogus")]})
    assert [p.metric for p in validate_summary(s).risks] == ["income_cv"]
    with pytest.raises(GeminiError):
        validate_summary(_summary(risk_metric="bogus"))


def test_stub_summary_is_valid():
    facts = {"grade": "B", "recommendation": "favorable", "sources": [{}, {}],
             "metrics": {"avg_monthly_net": "1000.00", "income_cv": 0.12}}
    s = stub_summary(facts, "id")
    assert validate_summary(s) and "Grade B" in s.headline and s.customer_explanation_local != s.customer_explanation_en


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append((model, contents, config))
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return SimpleNamespace(text=o)


def test_vertex_retries_once_then_parses():
    good = json.dumps(ext([row("2026-09-01", 7)]).model_dump())
    fake = SimpleNamespace(models=FakeModels([RuntimeError("503"), good]))
    sleeps = []
    g = VertexGemini(Settings(gemini_model="m-test"), client=fake, sleep=sleeps.append)
    out = g.extract_document(b"%PDF", "application/pdf", filename="a.pdf", country="VN", reference_date=REF)
    assert out.rows[0].amount == 7 and sleeps == [2] and len(fake.models.calls) == 2
    assert fake.models.calls[0][0] == "m-test"


def test_vertex_raises_after_second_failure():
    fake = SimpleNamespace(models=FakeModels([RuntimeError("a"), "not json"]))
    with pytest.raises(GeminiError):
        VertexGemini(Settings(), client=fake, sleep=lambda s: None).map_csv_columns(
            ["Tgl"], [["01-01-2026"]], filename="x.csv", country="ID")


def test_vertex_summarize_validates():
    bad = _summary(strength_metric="bogus").model_dump_json()
    fake = SimpleNamespace(models=FakeModels([bad]))
    with pytest.raises(GeminiError):
        VertexGemini(Settings(), client=fake, sleep=lambda s: None).summarize({"x": 1}, purpose="loan", language="vi")


def test_prompts_format_without_key_errors():
    assert "Indonesia" in prompts.EXTRACT_PROMPT.format(country_name="Indonesia", reference_date="2026-10-18")
    assert "Tgl" in prompts.CSV_MAPPING_PROMPT.format(country_name="Indonesia", header='["Tgl"]', rows="[]")
    assert "{" in prompts.JSON_MAP_PROMPT.format(country_name="Vietnam", reference_date="2026-10-18", payload="{}")
    assert "Filipino" in prompts.SUMMARY_PROMPT.format(purpose="loan", metric_keys="a, b", language_name="Filipino",
                                                       json="{}")


def test_dropped_rows_keep_original_positions():
    e = ext([row("2026-09-01", 100, balance=1100), row("bad", 40, balance=1140), row("2026-09-03", 50, balance=1190)])
    txns = extraction_to_transactions(e, source_id="s", currency="IDR", reference_date=REF)
    assert [t.row_index for t in txns] == [0, 2]
    from app.services.tamper import check
    assert check(txns) == []


class Mono:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_vertex_skips_retry_when_deadline_would_pass():
    mono = Mono()

    class SlowFail(FakeModels):
        def generate_content(self, **kw):
            mono.t += 30  # first attempt burned 30 s before failing
            return super().generate_content(**kw)

    fake = SimpleNamespace(models=SlowFail([RuntimeError("timeout"), "unused"]))
    g = VertexGemini(Settings(), client=fake, sleep=lambda s: None, monotonic=mono)
    with pytest.raises(GeminiError):
        g.map_csv_columns(["Tgl"], [["01-01-2026"]], filename="x.csv", country="ID")
    assert len(fake.models.calls) == 1


def test_vertex_config_disables_thinking_for_mapping_and_summary():
    good = json.dumps({"date_column": "Tgl", "date_format": "%d-%m-%Y", "amount_column": "A", "debit_column": None,
                       "credit_column": None, "direction_column": None, "direction_in_values": [],
                       "description_column": None, "balance_column": None, "counterparty_column": None,
                       "thousands_separator": "none", "decimal_separator": ",", "channel": "qris",
                       "status_column": None, "success_values": []})
    fake = SimpleNamespace(models=FakeModels([good]))
    VertexGemini(Settings(), client=fake, sleep=lambda s: None).map_csv_columns(
        ["Tgl"], [["01-01-2026"]], filename="x.csv", country="ID")
    assert fake.models.calls[0][2].thinking_config.thinking_budget == 0


def test_gemini_timeout_fits_hosting_limit():
    from app.config import GEMINI_DEADLINE_S, GEMINI_TIMEOUT_S
    assert GEMINI_TIMEOUT_S * 2 + 2 > GEMINI_DEADLINE_S  # a slow first attempt never gets a second
    assert GEMINI_DEADLINE_S <= 55
