from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Direction = Literal["in", "out"]
Channel = Literal["bank", "ewallet", "qris", "card", "cash", "other"]
TxnKind = Literal["normal", "returned", "loan_repayment", "internal_transfer"]
Trust = Literal["verified", "extracted"]
SourceKind = Literal["open_finance", "api_push", "upload", "camera"]
Status = Literal["created", "needs_more_data", "scored", "reviewed", "error"]
Recommendation = Literal["favorable", "review", "unfavorable"]
Country = Literal["ID", "PH", "VN"]

METRIC_KEYS = (
    "months_covered", "avg_monthly_inflow", "avg_monthly_outflow", "avg_monthly_net", "income_cv",
    "net_margin", "trend_pct", "returned_count", "debt_burden", "verified_share", "top_payer_share",
    "tamper_flag_count", "coverage_ratio",
)


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Transaction(BaseModel):
    id: str
    date: dt.date
    amount: Decimal = Field(gt=0)
    direction: Direction
    description: str = ""
    channel: Channel = "other"
    counterparty: str | None = None
    balance: Decimal | None = None
    currency: str
    kind: TxnKind = "normal"
    source_id: str
    row_index: int
    duplicate_of: str | None = None


class Customer(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: Literal["individual", "business"]
    occupation_or_business_type: str = Field(min_length=1, max_length=120)
    country: Country
    years_active: float = Field(ge=0)


class Consent(BaseModel):
    ref: str
    provider: str = "openfinance-sea-sim"
    granted_at: dt.datetime
    expires_at: dt.datetime


class TamperFlag(BaseModel):
    row_index: int
    expected_balance: Decimal
    actual_balance: Decimal


class Source(BaseModel):
    id: str
    kind: SourceKind
    label: str
    trust: Trust
    txn_count: int
    months_covered: int
    tamper_flags: list[TamperFlag] = Field(default_factory=list)
    added_at: dt.datetime


class Sufficiency(BaseModel):
    months_covered: int
    inflow_txn_count: int
    sufficient: bool
    reasons: list[str] = Field(default_factory=list)


class CollectionItem(BaseModel):
    id: str
    kind: Literal["upload", "camera"]
    filename: str
    mime_type: str
    status: Literal["done", "failed"]
    txn_count: int = 0
    source_id: str | None = None
    error: str | None = None
    added_at: dt.datetime


class Collection(BaseModel):
    token_hash: str
    created_at: dt.datetime
    expires_at: dt.datetime
    completed_at: dt.datetime | None = None
    items: list[CollectionItem] = Field(default_factory=list)


class MonthlyRow(BaseModel):
    month: str
    inflow: Decimal
    outflow: Decimal
    net: Decimal


class Metrics(BaseModel):
    months_covered: int
    avg_monthly_inflow: Decimal
    avg_monthly_outflow: Decimal
    avg_monthly_net: Decimal
    income_cv: float
    net_margin: float
    trend_pct: float
    returned_count: int
    debt_burden: float
    verified_share: float
    top_payer_share: float | None
    tamper_flag_count: int
    monthly: list[MonthlyRow]


class ScoreBreakdown(BaseModel):
    stability: int
    margin: int
    trend: int
    returned: int
    debt: int
    trust: int
    concentration_penalty: int
    tamper_penalty: int


class Point(BaseModel):
    point: str
    metric: str


class AiSummary(BaseModel):
    headline: str
    summary: str
    strengths: list[Point]
    risks: list[Point]
    data_notes: list[str]
    next_steps: list[str]
    customer_explanation_local: str
    customer_explanation_en: str


class Result(BaseModel):
    metrics: Metrics
    score: int
    grade: Literal["A", "B", "C", "D"]
    breakdown: ScoreBreakdown
    recommendation: Recommendation
    limited_data: bool
    max_monthly_commitment: Decimal
    installment: Decimal | None
    coverage_ratio: float | None
    suggested_max_amount: Decimal | None
    ai_summary: AiSummary | None = None
    computed_at: dt.datetime


class Review(BaseModel):
    analyst_email: str
    action: Literal["accept", "override"]
    final_recommendation: Recommendation
    note: str = ""
    at: dt.datetime


class Event(BaseModel):
    at: dt.datetime
    actor: str
    type: str
    detail: dict = Field(default_factory=dict)


class Assessment(BaseModel):
    id: str
    client_id: str
    external_ref: str | None = None
    customer: Customer
    purpose: str
    requested_amount: Decimal | None = None
    tenor_months: int | None = None
    currency: str
    consent: Consent
    status: Status
    error: str | None = None
    sufficiency: Sufficiency | None = None
    collection: Collection | None = None
    sources: list[Source] = Field(default_factory=list)
    result: Result | None = None
    review: Review | None = None
    events: list[Event] = Field(default_factory=list)
    created_at: dt.datetime
    updated_at: dt.datetime


# ---- Gemini response schemas (no defaults: Gemini response_schema must not carry default values) ----
class ExtractedRow(BaseModel):
    date: str
    description: str
    amount: float
    direction: Direction
    balance: float | None
    counterparty: str | None
    kind: Literal["normal", "returned", "loan_repayment"]


class Extraction(BaseModel):
    document_type: Literal["bank_statement", "ewallet_history", "qris_report", "cash_ledger", "receipt", "other"]
    channel: Channel
    institution: str | None
    currency: str | None
    rows: list[ExtractedRow]


class CsvMapping(BaseModel):
    date_column: str
    date_format: str
    amount_column: str | None
    debit_column: str | None
    credit_column: str | None
    direction_column: str | None
    direction_in_values: list[str]
    description_column: str | None
    balance_column: str | None
    counterparty_column: str | None
    thousands_separator: Literal[".", ",", " ", "none"]
    decimal_separator: Literal[".", ","]
    channel: Channel
    status_column: str | None
    success_values: list[str]


# ---- API request models ----
class StandardTxnIn(BaseModel):
    date: dt.date
    amount: Decimal = Field(gt=0)
    direction: Direction
    description: str = ""
    channel: Channel = "other"
    counterparty: str | None = None
    balance: Decimal | None = None
    kind: Literal["normal", "returned", "loan_repayment"] = "normal"


class ConsentIn(BaseModel):
    ref: str = Field(min_length=1, max_length=120)
    provider: str = "openfinance-sea-sim"


class CreateAssessmentRequest(BaseModel):
    external_ref: str | None = Field(default=None, max_length=120)
    customer: Customer
    purpose: str = Field(min_length=1, max_length=40)
    requested_amount: Decimal | None = Field(default=None, gt=0)
    tenor_months: int | None = Field(default=None, ge=1, le=120)
    consent: ConsentIn


class PushSourceRequest(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    format: Literal["standard", "auto"]
    transactions: list[StandardTxnIn] | None = None
    payload: Any = None

    @model_validator(mode="after")
    def _check_body(self):
        if self.format == "standard" and not self.transactions:
            raise ValueError("format=standard requires a non-empty transactions list")
        if self.format == "auto" and self.payload is None:
            raise ValueError("format=auto requires payload")
        return self


class ReviewRequest(BaseModel):
    action: Literal["accept", "override"]
    final_recommendation: Recommendation | None = None
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _check_override(self):
        if self.action == "override" and self.final_recommendation is None:
            raise ValueError("override requires final_recommendation")
        return self


class Analyst(BaseModel):
    uid: str
    email: str
