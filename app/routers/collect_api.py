from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.config import MAX_FILE_BYTES
from app.deps import Services, get_services

router = APIRouter(prefix="/api/collect", include_in_schema=False)


@router.get("/{token}")
def info(token: str, s: Services = Depends(get_services)):
    return s.assessments.collect_info(token)


@router.post("/{token}/items")
def add_item(token: str, file: UploadFile = File(...), kind: Literal["upload", "camera"] = Form("upload"),
             s: Services = Depends(get_services)):
    data = file.file.read(MAX_FILE_BYTES + 1)
    item = s.assessments.add_item(token, data=data, filename=file.filename or "file",
                                  mime_type=file.content_type or "", kind=kind)
    if item.status == "done":
        return {"item_id": item.id, "status": "done", "txn_count": item.txn_count}
    return {"item_id": item.id, "status": "failed", "message_key": "extract_failed"}


@router.post("/{token}/complete")
def complete(token: str, s: Services = Depends(get_services)):
    s.assessments.complete(token)
    return {"status": "received"}
