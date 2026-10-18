from datetime import timedelta

from app.services import merge, sufficiency
from tests.factories import T0, src, tx


def test_duplicate_across_sources_keeps_verified():
    a = tx("2026-08-14", 1000, source="bank")
    b = tx("2026-08-14", 1000, source="csv")
    out = merge.apply([b, a], [src("bank", trust="verified"), src("csv", trust="extracted")])
    by = {t.source_id: t for t in out}
    assert by["bank"].duplicate_of is None
    assert by["csv"].duplicate_of == by["bank"].id
    assert len(merge.effective(out)) == 1


def test_same_source_identical_rows_are_not_duplicates():
    out = merge.apply([tx("2026-08-14", 1000, row=0), tx("2026-08-14", 1000, row=1)], [src("s1")])
    assert all(t.duplicate_of is None for t in out)


def test_equal_trust_prefers_earliest_added_source():
    out = merge.apply(
        [tx("2026-08-14", 5, source="late"), tx("2026-08-14", 5, source="early")],
        [src("late", trust="extracted", added_at=T0 + timedelta(hours=1)), src("early", trust="extracted")])
    assert {t.source_id: t.duplicate_of is None for t in out} == {"early": True, "late": False}


def test_internal_transfer_same_and_next_day_one_pair_each():
    bank1 = tx("2026-09-03", 500, "out", source="bank", channel="bank")
    bank2 = tx("2026-09-17", 500, "out", source="bank", channel="bank", row=1)
    w1 = tx("2026-09-03", 500, "in", source="wal", channel="ewallet")
    w2 = tx("2026-09-18", 500, "in", source="wal", channel="ewallet", row=1)
    w3 = tx("2026-09-18", 500, "in", source="wal", channel="ewallet", row=2)
    out = merge.apply([bank1, bank2, w1, w2, w3], [src("bank"), src("wal", trust="extracted")])
    kinds = [t.kind for t in out]
    assert kinds.count("internal_transfer") == 4
    assert kinds.count("normal") == 1


def test_two_day_gap_and_loan_rows_are_not_transfers():
    out = merge.apply(
        [tx("2026-09-03", 500, "out", source="bank", channel="bank"),
         tx("2026-09-05", 500, "in", source="wal", channel="ewallet"),
         tx("2026-09-10", 400, "out", source="bank", channel="bank", kind="loan_repayment", row=1),
         tx("2026-09-10", 400, "in", source="wal", channel="ewallet", row=1)],
        [src("bank"), src("wal", trust="extracted")])
    assert all(t.kind != "internal_transfer" for t in out)


def test_merge_is_idempotent():
    rows = [tx("2026-09-03", 500, "out", source="bank", channel="bank"),
            tx("2026-09-03", 500, "in", source="wal", channel="ewallet"),
            tx("2026-08-14", 9, source="bank", row=1), tx("2026-08-14", 9, source="wal", row=1)]
    sources = [src("bank"), src("wal", trust="extracted")]
    once = merge.apply(rows, sources)
    twice = merge.apply(once, sources)
    assert [(t.kind, t.duplicate_of) for t in once] == [(t.kind, t.duplicate_of) for t in twice]


def test_sufficiency_thresholds_and_exclusions():
    rows = [tx(f"2026-{m:02d}-{d:02d}", 10, row=i) for i, (m, d) in
            enumerate((m, d) for m in range(4, 10) for d in (1, 2, 3, 4))]
    ok = sufficiency.evaluate(merge.apply(rows, [src("s1")]))
    assert ok.sufficient and ok.months_covered == 6 and ok.inflow_txn_count == 24 and ok.reasons == []
    thin = sufficiency.evaluate(rows[-6:])
    assert not thin.sufficient
    assert thin.reasons == ["Only 2 of 6 required months covered", "Only 6 of 20 required incoming transactions"]
    dup = rows[:1] + [tx("2026-04-01", 10, source="s2")]
    merged = merge.apply(dup, [src("s1"), src("s2", trust="extracted")])
    assert sufficiency.evaluate(merged).inflow_txn_count == 1
