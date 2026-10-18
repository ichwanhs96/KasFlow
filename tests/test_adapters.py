import json
from datetime import date
from decimal import Decimal

import pytest

from app.models import CsvMapping, StandardTxnIn
from app.services import mock_provider
from app.services.adapters import csv_mapper, open_finance, standard
from tests.factories import T0

PAYLOAD = {"provider": "openfinance-sea-sim", "consent_ref": "of-sari-001", "accounts": [{
    "account_id": "acc_1", "institution": "Bank Merapi", "type": "bank", "currency": "IDR", "masked_number": "••4821",
    "transactions": [
        {"txn_id": "t1", "posted": "03/07/2026", "amt": "1250000.00", "cr_dr": "CR", "narrative": "TRF DARI UD MAKMUR",
         "category": "SALES", "running_bal": "8450000.00", "counterparty_name": "UD Makmur"},
        {"txn_id": "t2", "posted": "05/07/2026", "amt": "400000.00", "cr_dr": "DR", "narrative": "ANGSURAN KOPERASI",
         "category": "LOAN", "running_bal": "8050000.00", "counterparty_name": None}]}]}

QRIS_MAPPING = CsvMapping(
    date_column="Tgl Transaksi", date_format="%d-%m-%Y", amount_column="Nominal (Rp)", debit_column=None,
    credit_column=None, direction_column=None, direction_in_values=[], description_column="Keterangan",
    balance_column=None, counterparty_column=None, thousands_separator=".", decimal_separator=",", channel="qris",
    status_column="Status", success_values=["BERHASIL"])


def test_open_finance_maps_provider_format():
    [(source, txns)] = open_finance.to_sources(PAYLOAD, default_currency="IDR", now=T0)
    assert source.label == "Bank Merapi ••4821" and source.trust == "verified" and source.kind == "open_finance"
    assert source.txn_count == 2 and source.tamper_flags == []
    t1, t2 = txns
    assert t1.date == date(2026, 7, 3) and t1.amount == Decimal("1250000.00") and t1.direction == "in"
    assert t1.channel == "bank" and t1.counterparty == "UD Makmur" and t1.balance == Decimal("8450000.00")
    assert t2.kind == "loan_repayment" and t2.direction == "out" and t2.source_id == source.id


def test_mock_provider_unknown_and_known_refs(tmp_path):
    assert mock_provider.fetch("nope", data_dir=tmp_path, now=T0)["accounts"] == []
    (tmp_path / "sari_open_finance.json").write_text(json.dumps(PAYLOAD))
    got = mock_provider.fetch("of-sari-001", data_dir=tmp_path, now=T0)
    assert got["accounts"][0]["institution"] == "Bank Merapi" and got["fetched_at"] == T0.isoformat()


def test_standard_rows_convert():
    rows = [StandardTxnIn(date="2026-09-01", amount="150000", direction="in", channel="bank")]
    [t] = standard.to_transactions(rows, source_id="s", currency="PHP")
    assert t.currency == "PHP" and t.source_id == "s" and t.row_index == 0 and t.amount == Decimal("150000")


def test_csv_mapper_qris_filters_failed_and_parses_amounts():
    data = ("Tgl Transaksi;Nominal (Rp);Status;Keterangan;ID Merchant\n"
            "01-04-2026;1.250.000;BERHASIL;Settlement QRIS;ID1\n"
            "02-04-2026;250.000;GAGAL;Transaksi gagal;ID1\n"
            "03-04-2026;980.500;BERHASIL;Settlement QRIS;ID1\n").encode()
    header, rows = csv_mapper.parse_csv(data)
    txns = csv_mapper.apply(header, rows, QRIS_MAPPING, source_id="q", currency="IDR")
    assert [t.amount for t in txns] == [Decimal("1250000"), Decimal("980500")]
    assert all(t.direction == "in" and t.channel == "qris" for t in txns)
    assert [t.row_index for t in txns] == [0, 1]


def test_parse_csv_handles_bom_cp1252_and_symbols():
    bom = "﻿Date,Amount,Desc\n01/09/2026,Rp 1.500,Café\n".encode("utf-8")
    header, rows = csv_mapper.parse_csv(bom)
    assert header == ["Date", "Amount", "Desc"] and rows[0][2] == "Café"
    cp = "Date;Amount;Desc\n01/09/2026;-2.000;Caf\xe9\n".encode("cp1252")
    header2, rows2 = csv_mapper.parse_csv(cp)
    assert header2 == ["Date", "Amount", "Desc"] and rows2[0][2] == "Café"
    m = QRIS_MAPPING.model_copy(update={"date_column": "Date", "date_format": "%d/%m/%Y", "amount_column": "Amount",
                                        "description_column": "Desc", "status_column": None, "success_values": []})
    [t] = csv_mapper.apply(header2, rows2, m, source_id="x", currency="IDR")
    assert t.direction == "out" and t.amount == Decimal("2000")
    assert csv_mapper.parse_amount("Rp 1.500", m) == Decimal("1500")
    with pytest.raises(ValueError):
        csv_mapper.parse_csv(b"\n\n")


def test_csv_debit_credit_columns_and_bad_rows_skipped():
    data = b"Tanggal,Debet,Kredit,Saldo\n01/09/2026,,100.00,1100.00\n02/09/2026,50.00,,1050.00\nnot-a-date,1,,\n"
    header, rows = csv_mapper.parse_csv(data)
    m = CsvMapping(date_column="Tanggal", date_format="%d/%m/%Y", amount_column=None, debit_column="Debet",
                   credit_column="Kredit", direction_column=None, direction_in_values=[], description_column=None,
                   balance_column="Saldo", counterparty_column=None, thousands_separator=",", decimal_separator=".",
                   channel="bank", status_column=None, success_values=[])
    txns = csv_mapper.apply(header, rows, m, source_id="b", currency="PHP")
    assert [(t.direction, t.amount, t.balance) for t in txns] == [
        ("in", Decimal("100.00"), Decimal("1100.00")), ("out", Decimal("50.00"), Decimal("1050.00"))]
