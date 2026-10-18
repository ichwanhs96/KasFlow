from datetime import datetime, timezone

import pytest

from app import seeding
from app.config import ASSETS_DIR, DATA_DIR, Settings
from app.repo import InMemoryRepo
from app.services.gemini import StubGemini
from app.services.pipeline import AssessmentService

NOW = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def svc():
    repo = InMemoryRepo()
    seeding.ensure_demo_client(repo, Settings())
    return AssessmentService(repo, StubGemini(), Settings(), clock=lambda: NOW)


def test_sari_thin_then_favorable_after_uploads(svc):
    a, url = svc.create("pinjamcepat", seeding.build_request(seeding.load_profile("sari"), "T-SARI"))
    assert a.status == "needs_more_data" and url and a.sufficiency.months_covered == 3
    done = seeding.run_persona(svc, "sari", external_ref="T-SARI-2")
    assert done.status == "scored" and done.result.grade in ("A", "B") and done.result.recommendation == "favorable"
    assert len(done.sources) == 4 and {s.kind for s in done.sources} == {"open_finance", "upload", "camera"}
    txns = svc.repo.get_transactions(done.id)
    assert sum(1 for t in txns if t.duplicate_of) == 2
    assert sum(1 for t in txns if t.kind == "internal_transfer") == 4
    assert done.result.metrics.tamper_flag_count == 0


def test_paolo_scored_immediately_as_review(svc):
    a = seeding.run_persona(svc, "paolo", external_ref="T-PAOLO")
    assert a.status == "scored" and a.collection is None
    assert a.result.grade == "C" and a.result.recommendation == "review"
    assert a.result.metrics.top_payer_share is None


def test_linh_unfavorable_with_two_tamper_flags(svc):
    a = seeding.run_persona(svc, "linh", external_ref="T-LINH")
    assert a.result.grade == "D" and a.result.recommendation == "unfavorable"
    assert a.result.metrics.tamper_flag_count == 2
    assert a.result.breakdown.concentration_penalty == -5


def test_persona_cards_and_seed_is_idempotent():
    cards = seeding.persona_cards()
    assert [c["id"] for c in cards] == ["sari", "paolo", "linh"] and cards[0]["currency"] == "IDR"
    repo = InMemoryRepo()
    svc = AssessmentService(repo, StubGemini(), Settings(), clock=lambda: NOW)
    seeding.seed(repo, svc, Settings())
    seeding.seed(repo, svc, Settings())
    refs = sorted(a.external_ref for a in repo.list_assessments())
    assert refs == ["SEED-LINH", "SEED-PAOLO"]
    assert (ASSETS_DIR / "linh_statement.pdf").exists() and (DATA_DIR / "extracted" / "sari_qris.csv.mapping.json").exists()
