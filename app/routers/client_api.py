from fastapi import APIRouter, Depends

from app.deps import Services, get_services, require_client
from app.models import CreateAssessmentRequest, PushSourceRequest
from app.views import public_assessment

router = APIRouter(prefix="/api/v1", tags=["assessments"])


@router.post("/assessments", status_code=201, summary="Create an assessment (fetches open-finance data first)")
def create_assessment(req: CreateAssessmentRequest, client: dict = Depends(require_client),
                      s: Services = Depends(get_services)):
    a, url = s.assessments.create(client["id"], req)
    return public_assessment(a, url)


@router.get("/assessments/{assessment_id}", summary="Get assessment status and result")
def get_assessment(assessment_id: str, client: dict = Depends(require_client), s: Services = Depends(get_services)):
    return public_assessment(s.assessments.get_for_client(client["id"], assessment_id))


@router.post("/assessments/{assessment_id}/sources", status_code=201,
             summary="Push additional data (standard format or any JSON with format=auto)")
def push_source(assessment_id: str, req: PushSourceRequest, client: dict = Depends(require_client),
                s: Services = Depends(get_services)):
    a, source, url = s.assessments.push_source(client["id"], assessment_id, req)
    return {"source_id": source.id, "txn_count": source.txn_count, **public_assessment(a, url)}


@router.post("/assessments/{assessment_id}/collection-link", summary="Issue a new customer collection link")
def new_collection_link(assessment_id: str, client: dict = Depends(require_client),
                        s: Services = Depends(get_services)):
    s.assessments.get_for_client(client["id"], assessment_id)
    a, url = s.assessments.issue_link(assessment_id, f"client:{client['id']}")
    return {"collection_url": url, "collection_expires_at": a.collection.expires_at.isoformat()}
