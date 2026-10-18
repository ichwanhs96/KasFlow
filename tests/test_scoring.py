from decimal import Decimal

import pytest

from app.services import scoring
from app.services.scoring import (
    debt_points, grade_for, margin_points, returned_points, stability_points, trend_points, trust_points,
)
from tests.factories import customer, src, tx


def monthly(inflows, outflows=None, *, start_month=4, source="s1", counterparty=None, desc=""):
    rows = []
    for i, amt in enumerate(inflows):
        m = start_month + i
        rows.append(tx(f"2026-{m:02d}-05", amt, "in", source=source, counterparty=counterparty, desc=desc, row=2 * i))
        if outflows:
            rows.append(tx(f"2026-{m:02d}-20", outflows[i], "out", source=source, row=2 * i + 1))
    return rows


def run(txns, *, cust=None, sources=None, amount=None, tenor=None, limited=False):
    return scoring.score(txns, customer=cust or customer(), sources=sources or [src("s1")],
                         requested_amount=Decimal(str(amount)) if amount else None, tenor_months=tenor,
                         limited_data=limited)


@pytest.mark.parametrize("cv,pts", [(0.0, 25), (0.20, 25), (0.2001, 15), (0.40, 15), (0.41, 8), (0.60, 8), (0.61, 0)])
def test_stability_bands(cv, pts):
    assert stability_points(cv) == pts


@pytest.mark.parametrize("m,pts", [(0.25, 25), (0.2499, 18), (0.15, 18), (0.05, 10), (0.0499, 5), (0.0001, 5), (0.0, 0), (-0.3, 0)])
def test_margin_bands(m, pts):
    assert margin_points(m) == pts


@pytest.mark.parametrize("t,pts", [(0.05, 15), (0.0499, 10), (-0.05, 10), (-0.0501, 4), (-0.20, 4), (-0.21, 0)])
def test_trend_bands(t, pts):
    assert trend_points(t) == pts


@pytest.mark.parametrize("n,pts", [(0, 15), (1, 10), (2, 4), (3, 4), (4, 0)])
def test_returned_bands(n, pts):
    assert returned_points(n) == pts


@pytest.mark.parametrize("d,pts", [(0.10, 10), (0.1001, 5), (0.30, 5), (0.31, 0)])
def test_debt_bands(d, pts):
    assert debt_points(d) == pts


@pytest.mark.parametrize("v,pts", [(0.70, 10), (0.6999, 6), (0.40, 6), (0.3999, 3), (0.0, 3)])
def test_trust_bands(v, pts):
    assert trust_points(v) == pts


@pytest.mark.parametrize("s,g", [(100, "A"), (80, "A"), (79, "B"), (65, "B"), (64, "C"), (50, "C"), (49, "D"), (0, "D")])
def test_grade_cutoffs(s, g):
    assert grade_for(s) == g


def test_stable_business_scores_95_favorable():
    r = run(monthly([10000] * 6, [7000] * 6))
    b = r.breakdown
    assert (b.stability, b.margin, b.trend, b.returned, b.debt, b.trust) == (25, 25, 10, 15, 10, 10)
    assert r.score == 95 and r.grade == "A" and r.recommendation == "favorable"
    assert r.metrics.avg_monthly_net == Decimal("3000.00")
    assert r.max_monthly_commitment == Decimal("2000.00")


def test_window_uses_last_six_months_with_data():
    rows = monthly([999999, 999999] + [10000] * 6, start_month=2)
    m = scoring.compute_metrics(rows, customer=customer(), sources=[src("s1")])
    assert m.months_covered == 6 and m.avg_monthly_inflow == Decimal("10000.00")
    assert [r.month for r in m.monthly] == [f"2026-{x:02d}" for x in range(4, 10)]


def test_cv_and_trend_values():
    m = scoring.compute_metrics(monthly([100, 100, 100, 110, 110, 110]), customer=customer(), sources=[src("s1")])
    assert m.trend_pct == pytest.approx(0.10)
    m2 = scoring.compute_metrics(monthly([10, 20]), customer=customer(), sources=[src("s1")])
    assert m2.income_cv == pytest.approx(5 / 15, abs=1e-4)
    assert m2.trend_pct == pytest.approx(1.0)


def test_empty_transactions_score_cleanly():
    r = run([], limited=True)
    assert r.metrics.months_covered == 0 and r.metrics.income_cv == 9.99
    assert r.score == 38 and r.grade == "D" and r.recommendation == "unfavorable"
    assert r.max_monthly_commitment == Decimal("0.00")


def test_tamper_penalty_and_downgrade():
    r = run(monthly([10000] * 6, [7000] * 6), sources=[src("s1", flags=[{"row_index": 1, "expected_balance": "1", "actual_balance": "2"}])])
    assert r.breakdown.tamper_penalty == -15 and r.score == 80 and r.grade == "A"
    assert r.recommendation == "review"


def test_limited_data_downgrades_favorable():
    assert run(monthly([10000] * 6, [7000] * 6), limited=True).recommendation == "review"


def test_concentration_penalty_business_only():
    rows = monthly([10000] * 6, [7000] * 6, counterparty="Shopmall")
    biz = run(rows, cust=customer("business"))
    ind = run(rows, cust=customer("individual"))
    assert biz.metrics.top_payer_share == pytest.approx(1.0) and biz.breakdown.concentration_penalty == -5
    assert ind.metrics.top_payer_share is None and ind.breakdown.concentration_penalty == 0


def test_returned_and_debt_detection_by_kind_and_regex():
    rows = monthly([10000] * 6, [7000] * 6)
    rows.append(tx("2026-09-21", 1000, "out", desc="Cicilan motor", row=50))
    rows.append(tx("2026-09-22", 10, "in", desc="TRANSFER RETURNED", row=51))
    rows.append(tx("2026-09-23", 10, "in", kind="returned", row=52))
    m = scoring.compute_metrics(rows, customer=customer(), sources=[src("s1")])
    assert m.returned_count == 2
    assert m.debt_burden == pytest.approx(1000 / 60020, abs=1e-4)


def test_verified_share_counts_by_source_trust():
    rows = monthly([10] * 6, source="v") + monthly([20] * 6, source="x")
    m = scoring.compute_metrics(rows, customer=customer(), sources=[src("v"), src("x", trust="extracted")])
    assert m.verified_share == pytest.approx(0.5)


def test_affordability_and_suggested_amount():
    rows = monthly([10_000_000] * 6, [7_000_000] * 6)
    r = run(rows, amount=50_000_000, tenor=12)
    assert abs(r.installment - Decimal("4584000")) < 5
    assert r.coverage_ratio == pytest.approx(3_000_000 / float(r.installment), rel=1e-3)
    assert r.coverage_ratio < 1.5
    assert Decimal("21800000") < r.suggested_max_amount < Decimal("21830000")
    assert r.recommendation == "review"
    ok = run(rows, amount=10_000_000, tenor=12)
    assert ok.suggested_max_amount is None and ok.recommendation == "favorable"
