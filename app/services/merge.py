from collections import defaultdict
from datetime import datetime, timezone

from app.models import Source, Transaction

_TRUST_RANK = {"verified": 0, "extracted": 1}
_FAR_FUTURE = datetime.max.replace(tzinfo=timezone.utc)


def effective(txns: list[Transaction]) -> list[Transaction]:
    return [t for t in txns if t.duplicate_of is None and t.kind != "internal_transfer"]


def apply(txns: list[Transaction], sources: list[Source]) -> list[Transaction]:
    by_id = {s.id: s for s in sources}

    def source_rank(source_id: str):
        s = by_id.get(source_id)
        return (_TRUST_RANK.get(s.trust, 2), s.added_at) if s else (3, _FAR_FUTURE)

    out = [t.model_copy(update={"duplicate_of": None,
                                "kind": "normal" if t.kind == "internal_transfer" else t.kind}) for t in txns]

    # 1) duplicates across different sources (same date, amount, direction)
    groups: dict[tuple, list[Transaction]] = defaultdict(list)
    for t in out:
        groups[(t.date, t.amount, t.direction)].append(t)
    for group in groups.values():
        per_source: dict[str, list[Transaction]] = defaultdict(list)
        for t in group:
            per_source[t.source_id].append(t)
        if len(per_source) < 2:
            continue
        ordered = sorted(per_source, key=source_rank)
        keepers = sorted(per_source[ordered[0]], key=lambda t: t.row_index)
        for sid in ordered[1:]:
            for keeper, dup in zip(keepers, sorted(per_source[sid], key=lambda t: t.row_index)):
                dup.duplicate_of = keeper.id

    # 2) internal transfers: bank out → e-wallet in, same amount, same or next day
    live = [t for t in out if t.duplicate_of is None and t.kind == "normal"]
    bank_outs = sorted((t for t in live if t.direction == "out" and t.channel == "bank"),
                       key=lambda t: (t.date, t.row_index))
    wallet_ins = sorted((t for t in live if t.direction == "in" and t.channel == "ewallet"),
                        key=lambda t: (t.date, t.row_index))
    used: set[str] = set()
    for o in bank_outs:
        for i in wallet_ins:
            if i.id in used:
                continue
            if i.amount == o.amount and 0 <= (i.date - o.date).days <= 1:
                o.kind = "internal_transfer"
                i.kind = "internal_transfer"
                used.add(i.id)
                break
    return out
