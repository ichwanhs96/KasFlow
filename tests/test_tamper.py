from decimal import Decimal

from app.services.sourcing import build_source, months_covered
from app.services.tamper import check
from tests.factories import T0, tx


def chain(rows):
    """rows: list of (direction, amount, balance) in row order."""
    return [tx(f"2026-09-{i + 1:02d}", a, d, balance=b, row=i) for i, (d, a, b) in enumerate(rows)]


def test_clean_chain_has_no_flags():
    assert check(chain([("in", 100, 1100), ("out", 50, 1050), ("in", 25, 1075)])) == []


def test_modified_amount_is_flagged_at_its_row():
    flags = check(chain([("in", 100, 1100), ("in", 130, 1150), ("out", 50, 1100)]))
    assert len(flags) == 1
    assert flags[0].row_index == 1
    assert flags[0].expected_balance == Decimal("1230") and flags[0].actual_balance == Decimal("1150")


def test_row_without_balance_resets_chain():
    rows = chain([("in", 100, 1100), ("in", 999, None), ("in", 50, 5000), ("in", 10, 5010)])
    assert check(rows) == []


def test_tolerance_of_one_unit():
    assert check(chain([("in", 100, 1100), ("in", 100, Decimal("1200.9"))])) == []
    assert len(check(chain([("in", 100, 1100), ("in", 100, Decimal("1201.5"))]))) == 1


def test_newest_first_statement_has_no_false_flags():
    # Chronological: +100 → 1100, -50 → 1050, +25 → 1075; printed newest first.
    rows = chain([("in", 25, 1075), ("out", 50, 1050), ("in", 100, 1100)])
    assert check(rows) == []


def test_build_source_counts_and_flags():
    txns = chain([("in", 100, 1100), ("in", 130, 1150)])
    s = build_source(id="s9", kind="upload", label="Upload: x.pdf", trust="extracted", txns=txns, now=T0)
    assert s.txn_count == 2 and s.months_covered == 1 and len(s.tamper_flags) == 1
    assert months_covered([tx("2026-08-01", 1), tx("2026-09-01", 1), tx("2026-09-05", 1)]) == 2


def test_dropped_row_gap_resets_chain():
    # Row 1 was dropped during extraction (bad date); rows 0 and 2 must not be compared.
    rows = [tx("2026-09-01", 100, balance=1100, row=0), tx("2026-09-03", 50, balance=1190, row=2)]
    assert check(rows) == []
