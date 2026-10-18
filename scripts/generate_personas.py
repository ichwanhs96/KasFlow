#!/usr/bin/env python3
"""Generate deterministic persona data, demo assets and stub fixtures, then verify persona targets.

Run from the repo root:  .venv/bin/python scripts/generate_personas.py
Exit code 1 if any persona misses its target (spec §10). Tuning knobs are the TARGETS/factors marked below.
"""
from __future__ import annotations

import csv
import io
import json
import random
import sys
import unicodedata
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

DATA = ROOT / "data" / "personas"
EXTRACTED = DATA / "extracted"
ASSETS = ROOT / "demo_assets"
FONTS = ROOT / "scripts" / "fonts"
PROVIDER = "openfinance-sea-sim"
MONTHS = [(2026, m) for m in range(4, 10)]  # Apr–Sep 2026
rng = random.Random(42)

UNICODE_FONTS = ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]
SANS_FONTS = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
HAND_FONTS = [str(FONTS / "Caveat.ttf"), "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
              "/System/Library/Fonts/Noteworthy.ttc"]


# ---------------- helpers ----------------
def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def days_of(y: int, m: int) -> list[date]:
    first = date(y, m, 1)
    nxt = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return [first + timedelta(days=i) for i in range((nxt - first).days)]


def split_amount(total: int, parts: int, unit: int) -> list[int]:
    weights = [rng.uniform(0.6, 1.4) for _ in range(parts)]
    s = sum(weights)
    raw = [int(total * w / s) // unit * unit for w in weights]
    raw[-1] += total - sum(raw)
    return raw


def rp(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def not_five(k: int) -> int:
    return (k if k % 5 else k + 1) * 1000


def fold(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def provider_account(institution, masked, typ, currency, rows, opening):
    txns, bal = [], opening
    for i, r in enumerate(sorted(rows, key=lambda r: r["d"])):
        bal = bal + r["amt"] if r["crdr"] == "CR" else bal - r["amt"]
        txns.append({"txn_id": f"t{i + 1}", "posted": r["d"].strftime("%d/%m/%Y"), "amt": f"{r['amt']}.00",
                     "cr_dr": r["crdr"], "narrative": r["narr"], "category": r["cat"], "running_bal": f"{bal}.00",
                     "counterparty_name": r.get("cp")})
    return {"account_id": f"acc_{masked[-4:]}", "institution": institution, "type": typ, "currency": currency,
            "masked_number": masked, "transactions": txns}


def extraction(document_type, channel, institution, currency, rows):
    return {"document_type": document_type, "channel": channel, "institution": institution, "currency": currency,
            "rows": rows}


def xrow(d: date, amount, direction, description, *, balance=None, counterparty=None, kind="normal"):
    return {"date": d.isoformat(), "description": description, "amount": amount, "direction": direction,
            "balance": balance, "counterparty": counterparty, "kind": kind}


def pil_font(size: int, handwriting: bool = False):
    for c in (HAND_FONTS if handwriting else []) + SANS_FONTS:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def fetch_caveat() -> None:
    dest = FONTS / "Caveat.ttf"
    if dest.exists():
        return
    try:
        urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf", dest)
    except Exception as e:  # noqa: BLE001 - optional nicety
        print(f"(Caveat font download skipped: {e}; using a fallback font)")


def pdf_font() -> tuple[str, bool]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path in UNICODE_FONTS:
        if not Path(path).exists():
            continue
        try:
            f = TTFont("KFUni", path)
            if all(ord(ch) in f.face.charToGlyph for ch in "ặộữđ"):
                pdfmetrics.registerFont(f)
                return "KFUni", True
        except Exception:  # noqa: BLE001
            continue
    return "Helvetica", False


# ---------------- renderers ----------------
def render_dompetku(rows, path: Path) -> None:
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 220], fill=(0, 150, 136))
    d.text((48, 60), "DompetKu", font=pil_font(64), fill="white")
    d.text((48, 150), "Riwayat Transaksi", font=pil_font(40), fill="white")
    y, big, small = 250, pil_font(40), pil_font(32)
    for dt, amt, direction, label in rows:
        d.ellipse([48, y + 10, 128, y + 90], fill=(224, 242, 241))
        d.text((74, y + 26), "+" if direction == "in" else "-", font=big, fill=(0, 120, 110))
        d.text((160, y + 8), label, font=big, fill=(30, 30, 30))
        d.text((160, y + 60), dt.strftime("%d %b %Y"), font=small, fill=(120, 120, 120))
        sign = "+" if direction == "in" else "-"
        d.text((W - 48, y + 30), f"{sign}Rp{rp(amt)}", font=big,
               fill=(0, 140, 70) if direction == "in" else (200, 40, 40), anchor="ra")
        d.line([48, y + 112, W - 48, y + 112], fill=(235, 235, 235), width=2)
        y += 115
    img.save(path)


def render_ledger(rows, path: Path) -> None:
    W, H = 1280, 960
    bg = Image.new("RGB", (W, H), (120, 82, 50))
    d = ImageDraw.Draw(bg)
    for i in range(0, H, 6):
        shade = 110 + rng.randrange(0, 25)
        d.line([0, i, W, i], fill=(shade, int(shade * 0.68), int(shade * 0.42)), width=3)
    paper = Image.new("RGB", (1040, 880), (250, 246, 232))
    p = ImageDraw.Draw(paper)
    hand, head = pil_font(30, True), pil_font(34, True)
    ink = (25, 35, 110)
    p.text((40, 20), "BUKU KAS - WARUNG BU SARI - SEPTEMBER 2026", font=head, fill=ink)
    cols = (40, 140, 640, 840)
    for x, label in zip(cols, ("Tgl", "Keterangan", "Masuk", "Keluar")):
        p.text((x, 80), label, font=head, fill=ink)
    for i in range(20):
        p.line([20, 159 + i * 38, 1020, 159 + i * 38], fill=(170, 190, 225), width=2)
    for x in (125, 625, 825):
        p.line([x, 70, x, 870], fill=(220, 120, 120), width=2)
    for i, (dt, amt, direction, label) in enumerate(rows):
        yy = 125 + i * 38
        p.text((cols[0], yy), f"{dt.day}/{dt.month}", font=hand, fill=ink)
        p.text((cols[1], yy), label, font=hand, fill=ink)
        p.text((cols[2] if direction == "in" else cols[3], yy), rp(amt), font=hand, fill=ink)
    paper = paper.rotate(-2, expand=True, fillcolor=(120, 82, 50))
    bg.paste(paper, ((W - paper.width) // 2, (H - paper.height) // 2))
    noise = Image.effect_noise((W, H), 18).convert("RGB")
    Image.blend(bg, noise, 0.06).filter(ImageFilter.GaussianBlur(0.6)).save(path)


def write_y4m(png: Path, out: Path, frames: int = 15) -> None:
    canvas = Image.new("RGB", (1280, 720), (30, 30, 30))
    img = Image.open(png).convert("RGB")
    img.thumbnail((1280, 720))
    canvas.paste(img, ((1280 - img.width) // 2, (720 - img.height) // 2))
    y, cb, cr = canvas.convert("YCbCr").split()
    frame = y.tobytes() + cb.resize((640, 360)).tobytes() + cr.resize((640, 360)).tobytes()
    with open(out, "wb") as f:
        f.write(b"YUV4MPEG2 W1280 H720 F15:1 Ip A1:1 C420jpeg\n")
        for _ in range(frames):
            f.write(b"FRAME\n")
            f.write(frame)


def render_statement(rows, path: Path, font: str, vn) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    h = ParagraphStyle("h", fontName=font, fontSize=14, leading=18)
    n = ParagraphStyle("n", fontName=font, fontSize=9, leading=12)
    data = [[vn("Ngày"), vn("Diễn giải"), vn("Ghi nợ"), vn("Ghi có"), vn("Số dư")]]
    for r in rows:
        data.append([r["d"].strftime("%d/%m/%Y"), r["desc"], rp(r["shown_amt"]) if r["crdr"] == "DR" else "",
                     rp(r["shown_amt"]) if r["crdr"] == "CR" else "", rp(r["bal"])])
    t = Table(data, colWidths=[62, 230, 75, 75, 80], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fa")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8d3df"))]))
    doc.build([Paragraph(vn("NGÂN HÀNG SÔNG HỒNG - SAO KÊ TÀI KHOẢN"), h),
               Paragraph(vn("Chủ tài khoản: Nguyễn Thị Linh · Số tài khoản: ••3390 · Từ 01/04/2026 đến 30/09/2026"), n),
               Paragraph(vn("Số dư đầu kỳ: ") + rp(150_000_000) + " VND", n), Spacer(1, 10), t])


# ---------------- personas ----------------
def gen_sari() -> None:
    qris = []
    for k, (y, m) in enumerate(MONTHS):
        base = 900_000 * (1.03 ** k)  # knob: growth per month
        for d in days_of(y, m):
            if d.weekday() != 6:
                qris.append((d, int(base * rng.uniform(0.75, 1.25)) // 1000 * 1000, "BERHASIL"))
    for d in (date(2026, 5, 9), date(2026, 7, 21), date(2026, 9, 12)):
        qris.append((d, 250_000, "GAGAL"))
    qris.sort(key=lambda r: r[0])
    dup_date, dup_amt, _ = next(r for r in qris if r[0] >= date(2026, 8, 14) and r[2] == "BERHASIL")

    bank = []
    payers = ["UD Makmur", "Toko Jaya Abadi"]
    for (y, m) in [(2026, 7), (2026, 8), (2026, 9)]:
        for j, day in enumerate((2, 9, 16, 23)):
            p = payers[j % 2]
            bank.append(dict(d=date(y, m, day), amt=rng.randrange(2_000_000, 3_500_001, 50_000), crdr="CR",
                             narr=f"TRF DARI {p.upper()}", cat="SALES", cp=p))
        for day in (4, 11, 18, 25, 28):
            bank.append(dict(d=date(y, m, day), amt=rng.randrange(1_500_000, 2_800_001, 50_000), crdr="DR",
                             narr="BAYAR SUPPLIER SEMBAKO", cat="OTHER", cp="CV Sumber Pangan"))
        bank.append(dict(d=date(y, m, 5), amt=400_000, crdr="DR", narr="ANGSURAN KOPERASI", cat="LOAN",
                         cp="Koperasi Sejahtera"))
    bank.append(dict(d=dup_date, amt=dup_amt, crdr="CR", narr="QRIS SETTLEMENT", cat="SALES", cp=None))
    for d in (date(2026, 9, 3), date(2026, 9, 17)):
        bank.append(dict(d=d, amt=500_000, crdr="DR", narr="TOPUP DOMPETKU", cat="TRANSFER", cp="DompetKu"))
    write_json(DATA / "sari_open_finance.json", {"provider": PROVIDER, "consent_ref": "of-sari-001", "accounts": [
        provider_account("Bank Merapi", "••4821", "bank", "IDR", bank, 8_000_000)]})

    wallet = [(date(2026, 9, 3), 500_000, "in", "Isi saldo dari Bank Merapi"),
              (date(2026, 9, 18), 500_000, "in", "Isi saldo dari Bank Merapi")]
    for day in (1, 6, 8, 12, 14, 21, 26):
        wallet.append((date(2026, 9, day), not_five(rng.randrange(21, 150)), "in", "Terima pembayaran"))
    for day, label in ((2, "Bayar listrik"), (10, "Beli pulsa"), (15, "Bayar air"), (20, "Bayar internet"),
                       (27, "Beli pulsa")):
        wallet.append((date(2026, 9, day), not_five(rng.randrange(21, 150)), "out", label))
    wallet.sort(key=lambda r: r[0], reverse=True)  # screenshots show newest first
    render_dompetku(wallet, ASSETS / "sari_dompetku.png")
    write_json(EXTRACTED / "sari_dompetku.png.json", extraction("ewallet_history", "ewallet", "DompetKu", "IDR",
               [xrow(d, a, dr, lb) for d, a, dr, lb in wallet]))

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(["Tgl Transaksi", "Nominal (Rp)", "Status", "Keterangan", "ID Merchant"])
    for d, amt, st in qris:
        w.writerow([d.strftime("%d-%m-%Y"), rp(amt), st, "Settlement QRIS" if st == "BERHASIL" else "Transaksi gagal",
                    "ID1029384756"])
    (ASSETS / "sari_qris.csv").write_text(buf.getvalue(), encoding="utf-8")
    write_json(EXTRACTED / "sari_qris.csv.mapping.json", {
        "date_column": "Tgl Transaksi", "date_format": "%d-%m-%Y", "amount_column": "Nominal (Rp)",
        "debit_column": None, "credit_column": None, "direction_column": None, "direction_in_values": [],
        "description_column": "Keterangan", "balance_column": None, "counterparty_column": None,
        "thousands_separator": ".", "decimal_separator": ",", "channel": "qris", "status_column": "Status",
        "success_values": ["BERHASIL"]})

    sales = ["Jual beras 5kg", "Jual minyak goreng", "Jual gula 2kg", "Jual telur 1 rak", "Jual mi instan 1 dus",
             "Jual kopi sachet", "Jual sabun", "Jual rokok", "Jual gas elpiji", "Jual air galon", "Jual tepung",
             "Jual susu kaleng"]
    ledger = [(date(2026, 9, 1 + i * 2), rng.randrange(10, 51) * 5000, "in", item) for i, item in enumerate(sales)]
    ledger += [(date(2026, 9, 3), 25_000, "out", "Beli gas elpiji"), (date(2026, 9, 5), 400_000, "out", "Cicilan koperasi"),
               (date(2026, 9, 8), 15_000, "out", "Beli plastik"), (date(2026, 9, 14), 150_000, "out", "Bayar listrik toko"),
               (date(2026, 9, 19), 10_000, "out", "Beli es batu"), (date(2026, 9, 25), 30_000, "out", "Ongkos angkut")]
    ledger.sort(key=lambda r: r[0])
    render_ledger(ledger, ASSETS / "sari_buku_kas.png")
    write_y4m(ASSETS / "sari_buku_kas.png", ASSETS / "sari_buku_kas.y4m")
    write_json(EXTRACTED / "sari_buku_kas.png.json", extraction("cash_ledger", "cash", None, "IDR", [
        xrow(d, a, dr, lb, kind="loan_repayment" if "Cicilan" in lb else "normal") for d, a, dr, lb in ledger]))

    write_json(DATA / "sari_profile.json", {
        "id": "sari", "label": "Bu Sari — Warung, Indonesia (thin open-finance data)",
        "customer": {"name": "Sari Wulandari", "type": "business", "occupation_or_business_type": "Warung (grocery kiosk)",
                     "country": "ID", "years_active": 6},
        "consent_ref": "of-sari-001", "purpose": "loan", "requested_amount": 50_000_000, "tenor_months": 12})


def gen_paolo() -> None:
    targets = [18_000, 33_000, 24_000, 16_000, 31_000, 26_000]  # knob: monthly payouts (drives CV and trend)
    wallet, bank = [], []
    for (y, m), total in zip(MONTHS, targets):
        for day, amt in zip((4, 11, 18, 25), split_amount(total, 4, 100)):
            wallet.append(dict(d=date(y, m, day), amt=amt, crdr="CR", narr="RIDE PLATFORM PAYOUT", cat="SALES",
                               cp="Ride platform"))
        spend = int(total * 0.72) // 100 * 100  # knob: spend ratio (drives margin)
        labels = ("FUEL - PETRON", "FOOD - CARINDERIA", "FUEL - PETRON", "LOAD", "FUEL - PETRON", "GROCERY")
        for day, amt, narr in zip((6, 9, 13, 20, 23, 27), split_amount(spend, 6, 100), labels):
            wallet.append(dict(d=date(y, m, day), amt=amt, crdr="DR", narr=narr, cat="OTHER", cp=None))
        bank.append(dict(d=date(y, m, 15), amt=3_500, crdr="DR", narr="LOAN HULOG - BANK LUZON", cat="LOAN",
                         cp="Bank Luzon"))
    bank.append(dict(d=date(2026, 8, 16), amt=3_500, crdr="CR", narr="RETURNED - INSUFFICIENT FUNDS", cat="RETURNED",
                     cp=None))
    bank.append(dict(d=date(2026, 8, 20), amt=3_500, crdr="DR", narr="LOAN HULOG - BANK LUZON (RETRY)", cat="LOAN",
                     cp="Bank Luzon"))
    write_json(DATA / "paolo_open_finance.json", {"provider": PROVIDER, "consent_ref": "of-paolo-001", "accounts": [
        provider_account("Bank Luzon", "••2210", "bank", "PHP", bank, 30_000),
        provider_account("PeraPay", "••7781", "ewallet", "PHP", wallet, 5_000)]})
    write_json(DATA / "paolo_profile.json", {
        "id": "paolo", "label": "Paolo — Ride-hailing driver, Philippines (full open-finance data)",
        "customer": {"name": "Paolo Reyes", "type": "individual", "occupation_or_business_type": "Ride-hailing driver",
                     "country": "PH", "years_active": 3},
        "consent_ref": "of-paolo-001", "purpose": "loan", "requested_amount": 80_000, "tenor_months": 6})


def gen_linh(font: str, vn) -> None:
    vimo = []
    for (y, m) in [(2026, 8), (2026, 9)]:
        for day in (3, 12, 22):
            vimo.append(dict(d=date(y, m, day), amt=rng.randrange(200, 501) * 10_000, crdr="CR",
                             narr=vn("Nhận tiền từ khách"), cat="SALES", cp=None))
        for day in (8, 25):
            vimo.append(dict(d=date(y, m, day), amt=rng.randrange(100, 301) * 10_000, crdr="DR",
                             narr=vn("Thanh toán phí vận chuyển"), cat="OTHER", cp=None))
    write_json(DATA / "linh_open_finance.json", {"provider": PROVIDER, "consent_ref": "of-linh-001", "accounts": [
        provider_account("ViMo", "••5502", "ewallet", "VND", vimo, 20_000_000)]})

    targets = [120_000_000, 60_000_000, 140_000_000, 50_000_000, 90_000_000, 45_000_000]  # knob: volatility/decline
    stmt = []
    for (y, m), total in zip(MONTHS, targets):
        shop = total * 6 // 10
        for day, amt in zip((5, 15, 25), split_amount(shop, 3, 100_000)):
            stmt.append(dict(d=date(y, m, day), amt=amt, crdr="CR", desc=vn("Thanh toán từ SÀN TMĐT SHOPMALL"),
                             cp=vn("SÀN TMĐT SHOPMALL"), kind="normal"))
        for day, amt in zip((8, 18, 28), split_amount(total - shop, 3, 100_000)):
            stmt.append(dict(d=date(y, m, day), amt=amt, crdr="CR", desc=vn("Chuyển khoản khách lẻ"),
                             cp=vn("Khách lẻ"), kind="normal"))
        out_total = int(total * 1.15) // 100_000 * 100_000  # knob: spend ratio (drives margin)
        stmt.append(dict(d=date(y, m, 10), amt=20_000_000, crdr="DR", desc=vn("Trả góp khoản vay kinh doanh"),
                         cp=vn("Ngân hàng Sông Hồng"), kind="loan_repayment"))
        for day, amt in zip((6, 16, 26), split_amount(out_total - 20_000_000, 3, 100_000)):
            stmt.append(dict(d=date(y, m, day), amt=amt, crdr="DR", desc=vn("Nhập hàng từ xưởng may"), cp=None,
                             kind="normal"))
    for d in (date(2026, 5, 20), date(2026, 8, 20)):
        stmt.append(dict(d=d, amt=5_000_000, crdr="CR", desc=vn("Hoàn trả giao dịch không thành công"), cp=None,
                         kind="returned"))
    stmt.sort(key=lambda r: r["d"])
    bal = 150_000_000
    for r in stmt:
        bal = bal + r["amt"] if r["crdr"] == "CR" else bal - r["amt"]
        r["bal"], r["shown_amt"] = bal, r["amt"]
    for target in (date(2026, 6, 15), date(2026, 8, 15)):  # tampered rows: amount inflated, balance untouched
        r = next(r for r in stmt if r["d"] == target and r["crdr"] == "CR")
        r["shown_amt"] = r["amt"] + 30_000_000
    render_statement(stmt, ASSETS / "linh_statement.pdf", font, vn)
    write_json(EXTRACTED / "linh_statement.pdf.json", extraction("bank_statement", "bank", vn("Ngân hàng Sông Hồng"),
               "VND", [xrow(r["d"], r["shown_amt"], "in" if r["crdr"] == "CR" else "out", r["desc"], balance=r["bal"],
                            counterparty=r["cp"], kind=r["kind"]) for r in stmt]))
    write_json(DATA / "linh_profile.json", {
        "id": "linh", "label": "Linh — Online shop, Vietnam (thin open-finance data)",
        "customer": {"name": "Nguyễn Thị Linh", "type": "business", "occupation_or_business_type": "Online fashion shop",
                     "country": "VN", "years_active": 2},
        "consent_ref": "of-linh-001", "purpose": "loan", "requested_amount": 150_000_000, "tenor_months": 12})


# ---------------- verification ----------------
TARGETS = {"sari": ({"A", "B"}, "favorable", 0), "paolo": ({"C"}, "review", 0), "linh": ({"D"}, "unfavorable", 2)}


def verify() -> bool:
    from app import seeding
    from app.config import Settings
    from app.repo import InMemoryRepo
    from app.services.gemini import StubGemini
    from app.services.pipeline import AssessmentService

    settings = Settings()
    repo = InMemoryRepo()
    svc = AssessmentService(repo, StubGemini(EXTRACTED), settings,
                            clock=lambda: datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc), data_dir=DATA)
    seeding.ensure_demo_client(repo, settings)
    ok = True
    for p in seeding.PERSONAS:
        a = seeding.run_persona(svc, p, external_ref=f"CHECK-{p}", assets_dir=ASSETS, data_dir=DATA)
        r = a.result
        m = r.metrics
        print(f"{p:6s} status={a.status} score={r.score} grade={r.grade} rec={r.recommendation} "
              f"tamper={m.tamper_flag_count} months={m.months_covered} cv={m.income_cv:.3f} "
              f"margin={m.net_margin:.3f} trend={m.trend_pct:.3f} debt={m.debt_burden:.3f} "
              f"verified={m.verified_share:.2f} top={m.top_payer_share} breakdown={r.breakdown.model_dump()}")
        grades, rec, tamper = TARGETS[p]
        if r.grade not in grades or r.recommendation != rec or m.tamper_flag_count != tamper:
            ok = False
            print(f"  ✗ expected grade in {sorted(grades)}, recommendation={rec}, tamper={tamper}")
    return ok


def main() -> int:
    for d in (DATA, EXTRACTED, ASSETS, FONTS):
        d.mkdir(parents=True, exist_ok=True)
    fetch_caveat()
    font, unicode_ok = pdf_font()
    vn = (lambda s: s) if unicode_ok else fold
    gen_sari()
    gen_paolo()
    gen_linh(font, vn)
    ok = verify()
    print("ALL PERSONA TARGETS MET" if ok else "PERSONA TARGETS NOT MET — tune the knobs marked in this script")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
