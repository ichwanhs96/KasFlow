import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.models import CsvMapping, Transaction, new_id

_SYMBOLS = ("Rp", "rp", "₱", "PHP", "IDR", "VND", "₫", "đ")


def parse_csv(data: bytes) -> tuple[list[str], list[list[str]]]:
    text = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4096]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ";" if sample.count(";") > sample.count(",") else ","
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim) if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("empty csv")
    return [h.strip() for h in rows[0]], rows[1:]


def parse_amount(raw: str, m: CsvMapping) -> Decimal | None:
    s = (raw or "").strip()
    for sym in _SYMBOLS:
        s = s.replace(sym, "")
    s = s.replace(" ", "").replace(" ", "")
    negative = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("-()+")
    if m.thousands_separator:
        s = s.replace(m.thousands_separator, "")
    if m.decimal_separator == ",":
        s = s.replace(",", ".")
    if not s:
        return None
    try:
        v = Decimal(s)
    except InvalidOperation:
        return None
    return -v if negative else v


def apply(header: list[str], rows: list[list[str]], m: CsvMapping, *, source_id: str, currency: str) -> list[Transaction]:
    idx = {h: i for i, h in enumerate(header)}

    def col(row: list[str], name: str | None) -> str:
        if not name or name not in idx or idx[name] >= len(row):
            return ""
        return row[idx[name]].strip()

    success = {v.strip().lower() for v in m.success_values}
    ins = {v.strip().lower() for v in m.direction_in_values}
    out: list[Transaction] = []
    for row in rows:
        if m.status_column and success and col(row, m.status_column).lower() not in success:
            continue
        try:
            d = datetime.strptime(col(row, m.date_column), m.date_format).date()
        except ValueError:
            continue
        if m.amount_column:
            v = parse_amount(col(row, m.amount_column), m)
            if v is None or v == 0:
                continue
            if m.direction_column:
                direction = "in" if col(row, m.direction_column).lower() in ins else "out"
            else:
                direction = "out" if v < 0 else "in"
            amount = abs(v)
        else:
            cr = parse_amount(col(row, m.credit_column), m) if m.credit_column else None
            dr = parse_amount(col(row, m.debit_column), m) if m.debit_column else None
            if cr:
                direction, amount = "in", abs(cr)
            elif dr:
                direction, amount = "out", abs(dr)
            else:
                continue
        balance = parse_amount(col(row, m.balance_column), m) if m.balance_column else None
        out.append(Transaction(
            id=new_id(), date=d, amount=amount, direction=direction, description=col(row, m.description_column),
            channel=m.channel, counterparty=col(row, m.counterparty_column) or None, balance=balance,
            currency=currency, kind="normal", source_id=source_id, row_index=len(out)))
    return out
