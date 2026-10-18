from app.config import MIN_INFLOW_TXNS, MIN_MONTHS
from app.models import Sufficiency, Transaction
from app.services.merge import effective
from app.services.sourcing import months_covered


def evaluate(txns: list[Transaction]) -> Sufficiency:
    eff = effective(txns)
    months = months_covered(eff)
    inflows = sum(1 for t in eff if t.direction == "in")
    reasons = []
    if months < MIN_MONTHS:
        reasons.append(f"Only {months} of {MIN_MONTHS} required months covered")
    if inflows < MIN_INFLOW_TXNS:
        reasons.append(f"Only {inflows} of {MIN_INFLOW_TXNS} required incoming transactions")
    return Sufficiency(months_covered=months, inflow_txn_count=inflows, sufficient=not reasons, reasons=reasons)
