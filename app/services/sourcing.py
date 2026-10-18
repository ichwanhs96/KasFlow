from datetime import datetime

from app.models import Source, Transaction
from app.services import tamper


def months_covered(txns: list[Transaction]) -> int:
    return len({(t.date.year, t.date.month) for t in txns})


def build_source(*, id: str, kind: str, label: str, trust: str, txns: list[Transaction], now: datetime) -> Source:
    return Source(id=id, kind=kind, label=label, trust=trust, txn_count=len(txns),
                  months_covered=months_covered(txns), tamper_flags=tamper.check(txns), added_at=now)
