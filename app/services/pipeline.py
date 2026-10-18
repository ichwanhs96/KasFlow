from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Callable

from app.config import (
    COLLECTION_TTL_HOURS, CONSENT_TTL_DAYS, DATA_DIR, MAX_FILE_BYTES, MAX_ITEMS, MAX_TXNS, Settings,
)
from app.errors import AppError
from app.i18n import currency_for, language_for
from app.models import (
    Analyst, Assessment, Collection, CollectionItem, Consent, CreateAssessmentRequest, Event, PushSourceRequest,
    Review, ReviewRequest, Source, Transaction, new_id, utcnow,
)
from app.repo import Repo
from app.services import merge, mock_provider, scoring, sufficiency
from app.services.adapters import csv_mapper, open_finance, standard
from app.services.gemini import GeminiDailyLimit, GeminiError, GeminiRateLimited, GeminiService, extraction_to_transactions
from app.services.sourcing import build_source
from app.services.tokens import collection_url, hash_secret, new_collection_token

BUSY_MESSAGE = "KasFlow is busy right now. Please try again in a minute."
DAILY_LIMIT_MESSAGE = "KasFlow has reached its daily demo limit. Please try again tomorrow."


def _limit_error(e: GeminiRateLimited) -> AppError:
    if isinstance(e, GeminiDailyLimit):
        return AppError(429, "daily_limit_reached", DAILY_LIMIT_MESSAGE)
    return AppError(429, "rate_limited", BUSY_MESSAGE)
ALLOWED_MIME = {"application/pdf", "image/png", "image/jpeg", "text/csv"}


def normalize_mime(filename: str, mime: str) -> str:
    mime = (mime or "").lower().split(";")[0].strip()
    if filename.lower().endswith(".csv"):
        return "text/csv"
    if mime == "image/jpg":
        return "image/jpeg"
    return mime


def summary_facts(a: Assessment) -> dict:
    r = a.result
    return {
        "customer": a.customer.model_dump(mode="json", exclude={"name"}),
        "purpose": a.purpose,
        "requested_amount": str(a.requested_amount) if a.requested_amount is not None else None,
        "tenor_months": a.tenor_months,
        "currency": a.currency,
        "metrics": r.metrics.model_dump(mode="json", exclude={"monthly"}),
        "monthly": [m.model_dump(mode="json") for m in r.metrics.monthly],
        "score": r.score, "grade": r.grade, "breakdown": r.breakdown.model_dump(),
        "recommendation": r.recommendation, "limited_data": r.limited_data,
        "max_monthly_commitment": str(r.max_monthly_commitment),
        "installment": str(r.installment) if r.installment is not None else None,
        "coverage_ratio": r.coverage_ratio,
        "suggested_max_amount": str(r.suggested_max_amount) if r.suggested_max_amount is not None else None,
        "sources": [{"label": s.label, "kind": s.kind, "trust": s.trust, "txn_count": s.txn_count,
                     "months_covered": s.months_covered, "tamper_flag_count": len(s.tamper_flags)} for s in a.sources],
        "sufficiency_reasons": a.sufficiency.reasons if a.sufficiency else [],
    }


class AssessmentService:
    def __init__(self, repo: Repo, gemini: GeminiService, settings: Settings, *,
                 clock: Callable = utcnow, data_dir: Path = DATA_DIR) -> None:
        self.repo = repo
        self.gemini = gemini
        self.settings = settings
        self.clock = clock
        self.data_dir = Path(data_dir)

    # ---------- helpers ----------
    def _event(self, a: Assessment, actor: str, type: str, **detail) -> None:
        a.events.append(Event(at=self.clock(), actor=actor, type=type, detail=detail))

    def get(self, id: str) -> Assessment:
        a = self.repo.get_assessment(id)
        if a is None:
            raise AppError(404, "not_found", "Assessment not found")
        return a

    def get_for_client(self, client_id: str, id: str) -> Assessment:
        a = self.get(id)
        if a.client_id != client_id:
            raise AppError(404, "not_found", "Assessment not found")
        return a

    def list(self, status: str | None = None) -> list[Assessment]:
        items = [a for a in self.repo.list_assessments() if status in (None, "", "all") or a.status == status]
        return sorted(items, key=lambda a: a.updated_at, reverse=True)

    def _issue_link(self, a: Assessment) -> str:
        raw, h = new_collection_token()
        now = self.clock()
        items = a.collection.items if a.collection else []
        a.collection = Collection(token_hash=h, created_at=now, expires_at=now + timedelta(hours=COLLECTION_TTL_HOURS),
                                  items=items)
        self._event(a, "system", "collection_link_issued", expires_at=a.collection.expires_at.isoformat())
        return collection_url(self.settings.public_base_url, raw)

    def _append_source(self, a: Assessment, source: Source, txns: list[Transaction]) -> None:
        existing = self.repo.get_transactions(a.id)
        if len(existing) + len(txns) > MAX_TXNS:
            raise AppError(422, "too_many_transactions", f"An assessment holds at most {MAX_TXNS} transactions")
        a.sources.append(source)
        self.repo.put_transactions(a.id, existing + txns)

    def _summarize(self, a: Assessment) -> None:
        try:
            a.result.ai_summary = self.gemini.summarize(summary_facts(a), purpose=a.purpose,
                                                        language=language_for(a.customer.country))
            self._event(a, "system", "summary_generated")
        except GeminiError as e:
            a.result.ai_summary = None
            self._event(a, "system", "summary_failed", message=str(e)[:200])

    def _score(self, a: Assessment, txns: list[Transaction]) -> None:
        result = scoring.score(txns, customer=a.customer, sources=a.sources, requested_amount=a.requested_amount,
                               tenor_months=a.tenor_months, limited_data=not a.sufficiency.sufficient,
                               now=self.clock())
        a.result = result
        a.review = None
        a.status = "scored"
        self._event(a, "system", "scored", score=result.score, grade=result.grade,
                    recommendation=result.recommendation)
        self._summarize(a)

    # ---------- use cases ----------
    def create(self, client_id: str, req: CreateAssessmentRequest) -> tuple[Assessment, str | None]:
        now = self.clock()
        a = Assessment(
            id=new_id(), client_id=client_id, external_ref=req.external_ref, customer=req.customer,
            purpose=req.purpose, requested_amount=req.requested_amount, tenor_months=req.tenor_months,
            currency=currency_for(req.customer.country),
            consent=Consent(ref=req.consent.ref, provider=req.consent.provider, granted_at=now,
                            expires_at=now + timedelta(days=CONSENT_TTL_DAYS)),
            status="created", created_at=now, updated_at=now)
        self._event(a, f"client:{client_id}", "created", purpose=req.purpose)
        payload = mock_provider.fetch(req.consent.ref, data_dir=self.data_dir, now=now)
        txns: list[Transaction] = []
        for source, source_txns in open_finance.to_sources(payload, default_currency=a.currency, now=now):
            a.sources.append(source)
            txns.extend(source_txns)
        self._event(a, "system", "open_finance_fetched", accounts=len(a.sources), transactions=len(txns))
        self.repo.create_assessment(a)
        self.repo.put_transactions(a.id, txns)
        return self.run(a.id)

    def run(self, id: str, *, force_score: bool = False) -> tuple[Assessment, str | None]:
        a = self.get(id)
        try:
            txns = merge.apply(self.repo.get_transactions(id), a.sources)
            self.repo.put_transactions(id, txns)
            a.sufficiency = sufficiency.evaluate(txns)
            url = None
            if not a.sufficiency.sufficient and not force_score:
                c = a.collection
                if c is None or c.completed_at is not None or c.expires_at <= self.clock():
                    url = self._issue_link(a)
                a.status = "needs_more_data"
            else:
                self._score(a, txns)
            self.repo.save_assessment(a)
            return a, url
        except AppError:
            raise
        except Exception as e:  # noqa: BLE001 - record any pipeline failure on the assessment
            a.status = "error"
            a.error = str(e)[:300]
            self._event(a, "system", "error", message=a.error)
            self.repo.save_assessment(a)
            raise AppError(500, "internal_error", "Assessment processing failed") from e

    def issue_link(self, id: str, actor: str) -> tuple[Assessment, str]:
        a = self.get(id)
        url = self._issue_link(a)
        self.repo.save_assessment(a)
        return a, url

    def push_source(self, client_id: str, id: str, req: PushSourceRequest) -> tuple[Assessment, Source, str | None]:
        a = self.get_for_client(client_id, id)
        now = self.clock()
        sid = new_id()
        if req.format == "standard":
            txns = standard.to_transactions(req.transactions, source_id=sid, currency=a.currency)
            trust = "verified"
        else:
            try:
                ext = self.gemini.map_json(req.payload, country=a.customer.country, reference_date=now.date())
            except GeminiRateLimited as e:
                raise _limit_error(e) from e
            except GeminiError as e:
                raise AppError(422, "unmappable_payload", "Could not find transactions in payload") from e
            txns = extraction_to_transactions(ext, source_id=sid, currency=a.currency, reference_date=now.date())
            trust = "extracted"
        if not txns:
            raise AppError(422, "no_transactions", "No transactions found in payload")
        source = build_source(id=sid, kind="api_push", label=req.label, trust=trust, txns=txns, now=now)
        self._append_source(a, source, txns)
        self._event(a, f"client:{client_id}", "source_pushed", source_id=sid, transactions=len(txns))
        self.repo.save_assessment(a)
        a, url = self.run(id)
        return a, source, url

    def resolve_token(self, token: str) -> Assessment:
        a = self.repo.find_by_token_hash(hash_secret(token or ""))
        if a is None or a.collection is None:
            raise AppError(404, "invalid_link", "This link is not valid")
        if self.clock() >= a.collection.expires_at:
            raise AppError(410, "expired_link", "This link has expired")
        if a.collection.completed_at is not None:
            raise AppError(409, "already_completed", "These records were already submitted")
        return a

    def collect_info(self, token: str) -> dict:
        a = self.resolve_token(token)
        client = self.repo.get_client(a.client_id) or {"name": a.client_id}
        return {
            "assessment_id": a.id, "client_name": client.get("name", a.client_id), "purpose": a.purpose,
            "customer_first_name": a.customer.name.split()[0], "country": a.customer.country,
            "language": language_for(a.customer.country), "expires_at": a.collection.expires_at.isoformat(),
            "max_items": MAX_ITEMS,
            "items": [{"id": i.id, "kind": i.kind, "filename": i.filename, "status": i.status,
                       "txn_count": i.txn_count} for i in a.collection.items],
        }

    def add_item(self, token: str, *, data: bytes, filename: str, mime_type: str, kind: str) -> CollectionItem:
        a = self.resolve_token(token)
        mime = normalize_mime(filename, mime_type)
        if mime not in ALLOWED_MIME:
            raise AppError(422, "unsupported_file", "Only PDF, PNG, JPG or CSV files are accepted")
        if not data:
            raise AppError(422, "empty_file", "The file is empty")
        if len(data) > MAX_FILE_BYTES:
            raise AppError(422, "file_too_large", "Files must be 5 MB or smaller")
        if len(a.collection.items) >= MAX_ITEMS:
            raise AppError(422, "too_many_items", f"At most {MAX_ITEMS} files per request")
        now = self.clock()
        ref = now.date()
        sid = new_id()
        item = CollectionItem(id=new_id(), kind=kind, filename=(filename or "file")[:120], mime_type=mime,
                              status="failed", added_at=now)
        try:
            if mime == "text/csv":
                header, rows = csv_mapper.parse_csv(data)
                mapping = self.gemini.map_csv_columns(header, rows[:10], filename=item.filename,
                                                      country=a.customer.country)
                txns = [t for t in csv_mapper.apply(header, rows, mapping, source_id=sid, currency=a.currency)
                        if ref - timedelta(days=730) <= t.date <= ref]
            else:
                ext = self.gemini.extract_document(data, mime, filename=item.filename, country=a.customer.country,
                                                   reference_date=ref)
                txns = extraction_to_transactions(ext, source_id=sid, currency=a.currency, reference_date=ref)
            if not txns:
                raise GeminiError("no transactions extracted")
        except GeminiRateLimited as e:
            raise _limit_error(e) from e
        except (GeminiError, ValueError) as e:
            item.error = "extract_failed"
            a.collection.items.append(item)
            self._event(a, "customer", "item_failed", filename=item.filename, reason=str(e)[:200])
            self.repo.save_assessment(a)
            return item
        label = f"{'Photo' if kind == 'camera' else 'Upload'}: {item.filename}"
        source = build_source(id=sid, kind=kind, label=label, trust="extracted", txns=txns, now=now)
        self._append_source(a, source, txns)
        item.status, item.txn_count, item.source_id, item.error = "done", len(txns), sid, None
        a.collection.items.append(item)
        merged = merge.apply(self.repo.get_transactions(a.id), a.sources)
        self.repo.put_transactions(a.id, merged)
        a.sufficiency = sufficiency.evaluate(merged)
        self._event(a, "customer", "item_added", filename=item.filename, transactions=len(txns))
        self.repo.save_assessment(a)
        return item

    def complete(self, token: str) -> Assessment:
        a = self.resolve_token(token)
        if not any(i.status == "done" for i in a.collection.items):
            raise AppError(422, "no_items", "Add at least one readable file first")
        a.collection.completed_at = self.clock()
        self._event(a, "customer", "collection_completed")
        self.repo.save_assessment(a)
        a, _ = self.run(a.id, force_score=True)
        return a

    def score_now(self, id: str, actor: str) -> Assessment:
        a = self.get(id)
        self._event(a, actor, "score_requested")
        self.repo.save_assessment(a)
        a, _ = self.run(id, force_score=True)
        return a

    def regenerate_summary(self, id: str, actor: str) -> Assessment:
        a = self.get(id)
        if a.result is None:
            raise AppError(409, "not_scored", "Assessment has not been scored yet")
        self._event(a, actor, "summary_requested")
        self._summarize(a)
        self.repo.save_assessment(a)
        return a

    def review(self, id: str, analyst: Analyst, req: ReviewRequest) -> Assessment:
        a = self.get(id)
        if a.result is None:
            raise AppError(409, "not_scored", "Assessment has not been scored yet")
        final = req.final_recommendation if req.action == "override" else a.result.recommendation
        a.review = Review(analyst_email=analyst.email, action=req.action, final_recommendation=final, note=req.note,
                          at=self.clock())
        a.status = "reviewed"
        self._event(a, f"analyst:{analyst.email}", "reviewed", action=req.action, final_recommendation=final)
        self.repo.save_assessment(a)
        return a
