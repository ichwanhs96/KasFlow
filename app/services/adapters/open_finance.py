from datetime import datetime
from decimal import Decimal

from app.models import Source, Transaction, new_id
from app.services.sourcing import build_source

CHANNEL = {"bank": "bank", "ewallet": "ewallet", "qris": "qris"}
CATEGORY_KIND = {"LOAN": "loan_repayment", "RETURNED": "returned"}


def to_sources(payload: dict, *, default_currency: str, now: datetime) -> list[tuple[Source, list[Transaction]]]:
    result = []
    for acc in payload.get("accounts", []):
        sid = new_id()
        channel = CHANNEL.get(acc.get("type"), "other")
        currency = acc.get("currency") or default_currency
        txns = []
        for i, r in enumerate(acc.get("transactions", [])):
            txns.append(Transaction(
                id=new_id(), date=datetime.strptime(r["posted"], "%d/%m/%Y").date(), amount=Decimal(r["amt"]),
                direction="in" if r["cr_dr"] == "CR" else "out", description=r.get("narrative", ""),
                channel=channel, counterparty=r.get("counterparty_name") or None,
                balance=Decimal(r["running_bal"]) if r.get("running_bal") else None, currency=currency,
                kind=CATEGORY_KIND.get(r.get("category"), "normal"), source_id=sid, row_index=i))
        label = f'{acc.get("institution", "Account")} {acc.get("masked_number", "")}'.strip()
        result.append((build_source(id=sid, kind="open_finance", label=label, trust="verified", txns=txns, now=now),
                       txns))
    return result
