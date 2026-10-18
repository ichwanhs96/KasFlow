from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models import Assessment, Consent, Customer, Source, Transaction, new_id

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


def tx(d, amount, direction="in", *, source="s1", channel="bank", kind="normal", desc="",
       counterparty=None, balance=None, row=0, currency="IDR"):
    return Transaction(
        id=new_id(), date=date.fromisoformat(d) if isinstance(d, str) else d, amount=Decimal(str(amount)),
        direction=direction, description=desc, channel=channel, counterparty=counterparty,
        balance=Decimal(str(balance)) if balance is not None else None, currency=currency, kind=kind,
        source_id=source, row_index=row)


def src(id="s1", *, trust="verified", kind="open_finance", added_at=T0, flags=()):
    return Source(id=id, kind=kind, label=id, trust=trust, txn_count=0, months_covered=0,
                  tamper_flags=list(flags), added_at=added_at)


def customer(type="business", country="ID"):
    return Customer(name="Test Customer", type=type, occupation_or_business_type="Shop", country=country,
                    years_active=3)


def assessment(**kw):
    now = kw.pop("now", T0)
    base = dict(id=new_id(), client_id="c1", customer=customer(), purpose="loan", currency="IDR",
                consent=Consent(ref="r", granted_at=now, expires_at=now + timedelta(days=30)),
                status="created", created_at=now, updated_at=now)
    base.update(kw)
    return Assessment(**base)
