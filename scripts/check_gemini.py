#!/usr/bin/env python3
"""Phase B: run live Gemini extraction on every demo asset and compare with fixtures; then run Sari end-to-end.

Env: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GEMINI_MODEL (ADC via `gcloud auth application-default login`).
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import seeding  # noqa: E402
from app.config import ASSETS_DIR, DATA_DIR, load_settings  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402
from app.services.adapters import csv_mapper  # noqa: E402
from app.services.gemini import VertexGemini  # noqa: E402
from app.services.pipeline import AssessmentService  # noqa: E402

DOCS = [("sari_dompetku.png", "image/png", "ID"), ("sari_buku_kas.png", "image/png", "ID"),
        ("linh_statement.pdf", "application/pdf", "VN")]


def main() -> int:
    settings = load_settings()
    g = VertexGemini(settings)
    ok = True
    for name, mime, country in DOCS:
        expected = len(json.loads((DATA_DIR / "extracted" / f"{name}.json").read_text())["rows"])
        got = len(g.extract_document((ASSETS_DIR / name).read_bytes(), mime, filename=name, country=country,
                                     reference_date=date(2026, 10, 18)).rows)
        good = abs(got - expected) <= 0.2 * expected
        ok &= good
        print(f"{'OK ' if good else 'BAD'} {name}: live={got} fixture={expected}")
    header, rows = csv_mapper.parse_csv((ASSETS_DIR / "sari_qris.csv").read_bytes())
    mapping = g.map_csv_columns(header, rows[:10], filename="sari_qris.csv", country="ID")
    n = len(csv_mapper.apply(header, rows, mapping, source_id="x", currency="IDR"))
    expected = sum(1 for r in rows if r[2] == "BERHASIL")
    good = n == expected
    ok &= good
    print(f"{'OK ' if good else 'BAD'} sari_qris.csv: live={n} expected={expected} mapping={mapping.model_dump()}")
    repo = InMemoryRepo()
    seeding.ensure_demo_client(repo, settings)
    a = seeding.run_persona(AssessmentService(repo, g, settings), "sari", external_ref="CHECK-SARI")
    good = a.result is not None and a.result.recommendation == "favorable"
    ok &= good
    print(f"{'OK ' if good else 'BAD'} sari end-to-end: {a.status} {a.result.grade if a.result else '-'} "
          f"{a.result.recommendation if a.result else '-'}; summary={'yes' if a.result and a.result.ai_summary else 'no'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
