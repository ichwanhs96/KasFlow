from dataclasses import dataclass

from fastapi import Request

from app.auth import Verifier
from app.config import Settings
from app.errors import AppError
from app.models import Analyst
from app.repo import Repo
from app.services.gemini import GeminiService
from app.services.pipeline import AssessmentService
from app.services.tokens import hash_secret


@dataclass
class Services:
    settings: Settings
    repo: Repo
    gemini: GeminiService
    verifier: Verifier
    assessments: AssessmentService


def get_services(request: Request) -> Services:
    return request.app.state.services


def require_analyst(request: Request) -> Analyst:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise AppError(401, "unauthorized", "Missing bearer token")
    return get_services(request).verifier.verify(header[7:].strip())


def require_client(request: Request) -> dict:
    key = request.headers.get("x-api-key")
    if not key:
        raise AppError(401, "unauthorized", "Missing X-API-Key header")
    client = get_services(request).repo.get_client_by_key_hash(hash_secret(key))
    if not client:
        raise AppError(401, "unauthorized", "Invalid API key")
    return client
