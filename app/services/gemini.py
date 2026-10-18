from __future__ import annotations

import json
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from app.config import DATA_DIR, GEMINI_DEADLINE_S, GEMINI_TIMEOUT_S, JSON_PAYLOAD_MAX_BYTES, Settings
from app.i18n import COUNTRY, CURRENCIES, LANGUAGE_NAME
from app.models import METRIC_KEYS, AiSummary, CsvMapping, Extraction, Point, Transaction, new_id
from app.services import prompts

CAMERA_FALLBACK_FIXTURE = "sari_buku_kas.png"
EXTRACT_THINKING_BUDGET = 512  # small budget for handwriting/multimodal; mapping and summaries use 0 (latency)


class GeminiError(Exception):
    pass


class GeminiService(Protocol):
    def extract_document(self, data: bytes, mime_type: str, *, filename: str, country: str,
                         reference_date: date) -> Extraction: ...
    def map_csv_columns(self, header: list[str], sample_rows: list[list[str]], *, filename: str,
                        country: str) -> CsvMapping: ...
    def map_json(self, payload: Any, *, country: str, reference_date: date) -> Extraction: ...
    def summarize(self, facts: dict, *, purpose: str, language: str) -> AiSummary: ...


def extraction_to_transactions(ext: Extraction, *, source_id: str, currency: str,
                               reference_date: date) -> list[Transaction]:
    earliest = reference_date - timedelta(days=730)
    cur = ext.currency.upper() if ext.currency and ext.currency.upper() in CURRENCIES else currency
    out: list[Transaction] = []
    for i, r in enumerate(ext.rows):
        try:
            d = date.fromisoformat(r.date)
        except ValueError:
            continue
        if d > reference_date or d < earliest or r.amount is None or r.amount <= 0:
            continue
        out.append(Transaction(
            id=new_id(), date=d, amount=Decimal(str(r.amount)), direction=r.direction,
            description=(r.description or "").strip(), channel=ext.channel,
            counterparty=(r.counterparty or "").strip() or None,
            balance=Decimal(str(r.balance)) if r.balance is not None else None, currency=cur, kind=r.kind,
            source_id=source_id, row_index=i))
    return out


def validate_summary(s: AiSummary) -> AiSummary:
    s = s.model_copy(update={"strengths": [p for p in s.strengths if p.metric in METRIC_KEYS],
                             "risks": [p for p in s.risks if p.metric in METRIC_KEYS]})
    if not s.strengths or not s.risks:
        raise GeminiError("summary is missing valid strengths or risks")
    return s


_STUB_TEXT = {
    "en": "Your records show regular money coming in. Tips: 1) Keep recording every sale. "
          "2) Keep business and personal money separate. 3) Pay instalments on time.",
    "id": "Catatan Anda menunjukkan pemasukan yang rutin. Tips: 1) Catat setiap penjualan. "
          "2) Pisahkan uang usaha dan pribadi. 3) Bayar cicilan tepat waktu.",
    "fil": "Makikita sa iyong mga talaan ang regular na pumapasok na pera. Mga tip: 1) Itala ang bawat benta. "
           "2) Ihiwalay ang pera ng negosyo sa personal. 3) Magbayad ng hulog sa tamang oras.",
    "vi": "Hồ sơ của bạn cho thấy dòng tiền vào đều đặn. Gợi ý: 1) Ghi lại mọi khoản bán hàng. "
          "2) Tách tiền kinh doanh và tiền cá nhân. 3) Trả góp đúng hạn.",
}


def stub_summary(facts: dict, language: str) -> AiSummary:
    m = facts.get("metrics", {})
    return AiSummary(
        headline=f"Grade {facts.get('grade')} — {facts.get('recommendation')} (stub summary, Gemini not called)",
        summary="Deterministic placeholder summary used when GEMINI_BACKEND=stub.",
        strengths=[Point(point=f"Average monthly net cash flow is {m.get('avg_monthly_net')}.", metric="avg_monthly_net")],
        risks=[Point(point=f"Income volatility (CV) is {m.get('income_cv')}.", metric="income_cv")],
        data_notes=[f"{len(facts.get('sources', []))} data sources were used."],
        next_steps=["Confirm the largest inflows with the customer."],
        customer_explanation_local=_STUB_TEXT.get(language, _STUB_TEXT["en"]),
        customer_explanation_en=_STUB_TEXT["en"],
    )


class StubGemini:
    def __init__(self, fixtures_dir: Path = DATA_DIR / "extracted") -> None:
        self.fixtures_dir = Path(fixtures_dir)

    def _load(self, name: str, model):
        p = self.fixtures_dir / f"{name}.json"
        if not p.exists():
            raise GeminiError(f"no stub fixture for {name}")
        return model.model_validate_json(p.read_text(encoding="utf-8"))

    def extract_document(self, data, mime_type, *, filename, country, reference_date):
        name = CAMERA_FALLBACK_FIXTURE if filename.startswith("photo-") else filename
        return self._load(name, Extraction)

    def map_csv_columns(self, header, sample_rows, *, filename, country):
        return self._load(f"{filename}.mapping", CsvMapping)

    def map_json(self, payload, *, country, reference_date):
        if isinstance(payload, dict) and "__stub_extraction__" in payload:
            return Extraction.model_validate(payload["__stub_extraction__"])
        raise GeminiError("stub cannot map arbitrary JSON")

    def summarize(self, facts, *, purpose, language):
        return stub_summary(facts, language)


class VertexGemini:
    """Real Gemini on Vertex AI. Unit-tested with a fake client; verified live against Vertex AI."""

    def __init__(self, settings: Settings, client=None, sleep=time.sleep, monotonic=time.monotonic) -> None:
        if client is None:
            from google import genai
            from google.genai import types

            client = genai.Client(vertexai=True, project=settings.project, location=settings.location,
                                  http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_S * 1000))
        self.client = client
        self.model = settings.gemini_model
        self.sleep = sleep
        self.monotonic = monotonic

    def _generate(self, contents: list, schema, thinking_budget: int = 0):
        from google.genai import types

        config = types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json",
                                             response_schema=schema,
                                             thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget))
        last: Exception | None = None
        start = self.monotonic()
        for attempt in range(2):
            try:
                resp = self.client.models.generate_content(model=self.model, contents=contents, config=config)
                return schema.model_validate_json(resp.text)
            except Exception as e:  # network, quota, timeout, or invalid JSON
                last = e
                # Retry only if a second full attempt still fits the deadline (Hosting cuts requests at 60 s).
                if attempt == 0 and self.monotonic() - start + 2 + GEMINI_TIMEOUT_S <= GEMINI_DEADLINE_S:
                    self.sleep(2)
                else:
                    break
        raise GeminiError(f"Gemini call failed: {last}") from last

    def extract_document(self, data, mime_type, *, filename, country, reference_date):
        from google.genai import types

        prompt = prompts.EXTRACT_PROMPT.format(country_name=COUNTRY[country]["name"],
                                               reference_date=reference_date.isoformat())
        return self._generate([types.Part.from_bytes(data=data, mime_type=mime_type), prompt], Extraction,
                              thinking_budget=EXTRACT_THINKING_BUDGET)

    def map_csv_columns(self, header, sample_rows, *, filename, country):
        prompt = prompts.CSV_MAPPING_PROMPT.format(country_name=COUNTRY[country]["name"],
                                                   header=json.dumps(header, ensure_ascii=False),
                                                   rows=json.dumps(sample_rows[:10], ensure_ascii=False))
        return self._generate([prompt], CsvMapping)

    def map_json(self, payload, *, country, reference_date):
        raw = json.dumps(payload, ensure_ascii=False)[:JSON_PAYLOAD_MAX_BYTES]
        prompt = prompts.JSON_MAP_PROMPT.format(country_name=COUNTRY[country]["name"],
                                                reference_date=reference_date.isoformat(), payload=raw)
        return self._generate([prompt], Extraction)

    def summarize(self, facts, *, purpose, language):
        prompt = prompts.SUMMARY_PROMPT.format(purpose=purpose, metric_keys=", ".join(METRIC_KEYS),
                                               language_name=LANGUAGE_NAME.get(language, "English"),
                                               json=json.dumps(facts, ensure_ascii=False))
        return validate_summary(self._generate([prompt], AiSummary))
