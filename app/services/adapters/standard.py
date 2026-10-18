from app.models import StandardTxnIn, Transaction, new_id


def to_transactions(rows: list[StandardTxnIn], *, source_id: str, currency: str) -> list[Transaction]:
    return [Transaction(id=new_id(), date=r.date, amount=r.amount, direction=r.direction,
                        description=r.description, channel=r.channel, counterparty=r.counterparty,
                        balance=r.balance, currency=currency, kind=r.kind, source_id=source_id, row_index=i)
            for i, r in enumerate(rows)]
