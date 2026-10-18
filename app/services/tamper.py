from decimal import Decimal

from app.models import TamperFlag, Transaction

TOLERANCE = Decimal("1")


def _flags_in_order(rows: list[Transaction]) -> list[TamperFlag]:
    flags: list[TamperFlag] = []
    prev: Transaction | None = None
    for t in rows:
        if t.balance is None:
            prev = None
            continue
        if prev is not None and abs(t.row_index - prev.row_index) != 1:
            prev = None  # a row between these two was dropped during extraction; the chain can't be checked
        if prev is not None:
            expected = prev.balance + t.amount if t.direction == "in" else prev.balance - t.amount
            if abs(expected - t.balance) > TOLERANCE:
                flags.append(TamperFlag(row_index=t.row_index, expected_balance=expected, actual_balance=t.balance))
        prev = t
    return flags


def check(txns: list[Transaction]) -> list[TamperFlag]:
    """Flag rows whose printed running balance does not reconcile.

    Statements may be printed oldest-first or newest-first; both orders are tried and the
    order with fewer mismatches wins (ties prefer printed order).
    """
    rows = sorted(txns, key=lambda t: t.row_index)
    forward = _flags_in_order(rows)
    backward = _flags_in_order(list(reversed(rows)))
    return forward if len(forward) <= len(backward) else backward
