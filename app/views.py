from app.models import Assessment


def _money(v):
    return str(v) if v is not None else None


def public_assessment(a: Assessment, collection_url: str | None = None) -> dict:
    r = a.result
    return {
        "id": a.id, "external_ref": a.external_ref, "status": a.status,
        "sufficiency": a.sufficiency.model_dump(mode="json") if a.sufficiency else None,
        "sources": [{"id": s.id, "kind": s.kind, "label": s.label, "trust": s.trust, "txn_count": s.txn_count,
                     "months_covered": s.months_covered, "tamper_flag_count": len(s.tamper_flags)} for s in a.sources],
        "result": None if r is None else {
            "score": r.score, "grade": r.grade, "recommendation": r.recommendation, "limited_data": r.limited_data,
            "max_monthly_commitment": _money(r.max_monthly_commitment), "installment": _money(r.installment),
            "coverage_ratio": r.coverage_ratio, "suggested_max_amount": _money(r.suggested_max_amount),
            "headline": r.ai_summary.headline if r.ai_summary else None,
            "customer_explanation_local": r.ai_summary.customer_explanation_local if r.ai_summary else None,
            "customer_explanation_en": r.ai_summary.customer_explanation_en if r.ai_summary else None,
        },
        "review": {"final_recommendation": a.review.final_recommendation, "at": a.review.at.isoformat()}
        if a.review else None,
        "collection_url": collection_url,
        "collection_expires_at": a.collection.expires_at.isoformat()
        if a.collection and a.status == "needs_more_data" else None,
    }


def console_summary(a: Assessment) -> dict:
    r = a.result
    return {
        "id": a.id, "external_ref": a.external_ref,
        "customer": {"name": a.customer.name, "type": a.customer.type, "country": a.customer.country},
        "purpose": a.purpose, "status": a.status,
        "score": r.score if r else None, "grade": r.grade if r else None,
        "recommendation": r.recommendation if r else None,
        "final_recommendation": a.review.final_recommendation if a.review else None,
        "updated_at": a.updated_at.isoformat(),
    }
