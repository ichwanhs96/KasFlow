import segno
from fastapi import APIRouter, Depends

from app.deps import Services, get_services, require_analyst
from app.models import Analyst, ReviewRequest
from app.views import console_summary

router = APIRouter(prefix="/api/console", include_in_schema=False)


@router.get("/me")
def me(analyst: Analyst = Depends(require_analyst)):
    return analyst.model_dump()


@router.get("/assessments")
def list_assessments(status: str | None = None, analyst: Analyst = Depends(require_analyst),
                     s: Services = Depends(get_services)):
    return {"items": [console_summary(a) for a in s.assessments.list(status)]}


@router.get("/assessments/{assessment_id}")
def detail(assessment_id: str, analyst: Analyst = Depends(require_analyst), s: Services = Depends(get_services)):
    return s.assessments.get(assessment_id).model_dump(mode="json")


@router.get("/assessments/{assessment_id}/transactions")
def transactions(assessment_id: str, analyst: Analyst = Depends(require_analyst), s: Services = Depends(get_services)):
    a = s.assessments.get(assessment_id)
    flagged = {(src.id, f.row_index) for src in a.sources for f in src.tamper_flags}
    items = [{**t.model_dump(mode="json"), "tampered": (t.source_id, t.row_index) in flagged}
             for t in sorted(s.repo.get_transactions(assessment_id), key=lambda t: (t.source_id, t.row_index))]
    return {"items": items}


@router.post("/assessments/{assessment_id}/collection-link")
def collection_link(assessment_id: str, analyst: Analyst = Depends(require_analyst),
                    s: Services = Depends(get_services)):
    a, url = s.assessments.issue_link(assessment_id, f"analyst:{analyst.email}")
    return {"collection_url": url, "collection_expires_at": a.collection.expires_at.isoformat(),
            "qr_svg": segno.make(url, error="m").svg_inline(scale=4, dark="#111827")}


@router.post("/assessments/{assessment_id}/score")
def score_now(assessment_id: str, analyst: Analyst = Depends(require_analyst), s: Services = Depends(get_services)):
    return s.assessments.score_now(assessment_id, f"analyst:{analyst.email}").model_dump(mode="json")


@router.post("/assessments/{assessment_id}/summary")
def regenerate_summary(assessment_id: str, analyst: Analyst = Depends(require_analyst),
                       s: Services = Depends(get_services)):
    return s.assessments.regenerate_summary(assessment_id, f"analyst:{analyst.email}").model_dump(mode="json")


@router.post("/assessments/{assessment_id}/review")
def review(assessment_id: str, req: ReviewRequest, analyst: Analyst = Depends(require_analyst),
           s: Services = Depends(get_services)):
    return s.assessments.review(assessment_id, analyst, req).model_dump(mode="json")
