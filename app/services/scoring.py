from __future__ import annotations

import re
import statistics
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from app.config import ANNUAL_RATE, COVERAGE_TARGET
from app.models import Customer, Metrics, MonthlyRow, Result, ScoreBreakdown, Source, Transaction, utcnow
from app.services.merge import effective

RETURNED_RE = re.compile(
    r"\b(bounce|bounced|returned|reversal|reversed|ditolak|dikembalikan|gagal|ibinalik|hoàn trả|trả lại)\b", re.I)
DEBT_RE = re.compile(r"\b(loan|cicilan|angsuran|installment|hulog|trả góp|khoản vay)\b", re.I)
CENT = Decimal("0.01")
ZERO = Decimal("0")


def _q(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def _month(t: Transaction) -> str:
    return f"{t.date.year:04d}-{t.date.month:02d}"


def stability_points(cv: float) -> int:
    return 25 if cv <= 0.20 else 15 if cv <= 0.40 else 8 if cv <= 0.60 else 0


def margin_points(m: float) -> int:
    return 25 if m >= 0.25 else 18 if m >= 0.15 else 10 if m >= 0.05 else 5 if m > 0 else 0


def trend_points(t: float) -> int:
    return 15 if t >= 0.05 else 10 if t >= -0.05 else 4 if t >= -0.20 else 0


def returned_points(n: int) -> int:
    return 15 if n == 0 else 10 if n == 1 else 4 if n <= 3 else 0


def debt_points(d: float) -> int:
    return 10 if d <= 0.10 else 5 if d <= 0.30 else 0


def trust_points(v: float) -> int:
    return 10 if v >= 0.70 else 6 if v >= 0.40 else 3


def grade_for(score: int) -> str:
    return "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"


def _trend(inflows: list[float]) -> float:
    m = len(inflows)
    if m < 2:
        return 0.0
    k = 3 if m >= 6 else m // 2
    prev = statistics.fmean(inflows[:k])
    last = statistics.fmean(inflows[-k:])
    return 0.0 if prev == 0 else last / prev - 1


def compute_metrics(txns: list[Transaction], *, customer: Customer, sources: list[Source]) -> Metrics:
    trust = {s.id: s.trust for s in sources}
    eff = effective(txns)
    months = sorted({_month(t) for t in eff})[-6:]
    month_set = set(months)
    window = [t for t in eff if _month(t) in month_set]

    monthly: list[MonthlyRow] = []
    for m in months:
        inflow = sum((t.amount for t in window if _month(t) == m and t.direction == "in"), ZERO)
        outflow = sum((t.amount for t in window if _month(t) == m and t.direction == "out"), ZERO)
        monthly.append(MonthlyRow(month=m, inflow=_q(inflow), outflow=_q(outflow), net=_q(inflow - outflow)))

    count = len(months)
    total_in = sum((r.inflow for r in monthly), ZERO)
    total_out = sum((r.outflow for r in monthly), ZERO)
    inflows = [float(r.inflow) for r in monthly]
    mean_in = statistics.fmean(inflows) if inflows else 0.0
    if mean_in == 0:
        cv = 9.99
    elif count == 1:
        cv = 0.0
    else:
        cv = statistics.pstdev(inflows) / mean_in

    returned = sum(1 for t in window if t.kind == "returned" or RETURNED_RE.search(t.description or ""))
    debt_out = sum((t.amount for t in window if t.direction == "out"
                    and (t.kind == "loan_repayment" or DEBT_RE.search(t.description or ""))), ZERO)
    verified = sum(1 for t in window if trust.get(t.source_id) == "verified")

    top_payer: float | None = None
    if customer.type == "business" and total_in > 0:
        with_cp = [t for t in window if t.direction == "in" and t.counterparty and t.counterparty.strip()]
        cp_total = sum((t.amount for t in with_cp), ZERO)
        if cp_total >= total_in * Decimal("0.5"):
            groups: dict[str, Decimal] = defaultdict(lambda: ZERO)
            for t in with_cp:
                groups[t.counterparty.strip().lower()] += t.amount
            top_payer = float(max(groups.values()) / total_in)

    def avg(x: Decimal) -> Decimal:
        return _q(x / count) if count else ZERO.quantize(CENT)

    return Metrics(
        months_covered=count,
        avg_monthly_inflow=avg(total_in),
        avg_monthly_outflow=avg(total_out),
        avg_monthly_net=avg(total_in - total_out),
        income_cv=round(cv, 4),
        net_margin=round(float((total_in - total_out) / total_in), 4) if total_in else 0.0,
        trend_pct=round(_trend(inflows), 4),
        returned_count=returned,
        debt_burden=round(float(debt_out / total_in), 4) if total_in else 0.0,
        verified_share=round(verified / len(window), 4) if window else 0.0,
        top_payer_share=round(top_payer, 4) if top_payer is not None else None,
        tamper_flag_count=sum(len(s.tamper_flags) for s in sources),
        monthly=monthly,
    )


def score(txns: list[Transaction], *, customer: Customer, sources: list[Source], requested_amount: Decimal | None,
          tenor_months: int | None, limited_data: bool, now: datetime | None = None) -> Result:
    m = compute_metrics(txns, customer=customer, sources=sources)
    b = ScoreBreakdown(
        stability=stability_points(m.income_cv),
        margin=margin_points(m.net_margin),
        trend=trend_points(m.trend_pct),
        returned=returned_points(m.returned_count),
        debt=debt_points(m.debt_burden),
        trust=trust_points(m.verified_share),
        concentration_penalty=-5 if m.top_payer_share is not None and m.top_payer_share > 0.5 else 0,
        tamper_penalty=-15 if m.tamper_flag_count > 0 else 0,
    )
    total = max(0, min(100, sum(b.model_dump().values())))
    grade = grade_for(total)
    rec = {"A": "favorable", "B": "favorable", "C": "review", "D": "unfavorable"}[grade]
    if rec == "favorable" and (m.tamper_flag_count > 0 or limited_data):
        rec = "review"

    max_commit = _q(max(ZERO, m.avg_monthly_net) / COVERAGE_TARGET)
    installment = coverage = suggested = None
    if requested_amount and tenor_months:
        r = ANNUAL_RATE / 12
        factor = 1 - (1 + r) ** -tenor_months
        installment = _q(requested_amount * r / factor)
        coverage = round(float(m.avg_monthly_net / installment), 4) if installment else None
        if coverage is not None and coverage < float(COVERAGE_TARGET):
            suggested = _q(max_commit * factor / r)
            if rec == "favorable":
                rec = "review"

    return Result(metrics=m, score=total, grade=grade, breakdown=b, recommendation=rec, limited_data=limited_data,
                  max_monthly_commitment=max_commit, installment=installment, coverage_ratio=coverage,
                  suggested_max_amount=suggested, ai_summary=None, computed_at=now or utcnow())
