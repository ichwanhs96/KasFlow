import json

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import seeding
from app.auth import FirebaseVerifier, StubVerifier
from app.config import STATIC_DIR, Settings, load_settings
from app.deps import Services
from app.errors import AppError
from app.models import utcnow
from app.repo import FirestoreRepo, InMemoryRepo
from app.routers import client_api, collect_api, console_api, demo, pages
from app.services.gemini import RateLimitedGemini, StubGemini, VertexGemini
from app.services.pipeline import AssessmentService
from app.services.ratelimit import DailyCap, SlidingWindowLimiter

API_DESCRIPTION = (
    "KasFlow turns open-finance data — plus any customer-supplied records — into a deterministic, explained "
    "credit assessment. Authenticate with the `X-API-Key` header.")


def build_services(settings: Settings, *, clock=utcnow) -> Services:
    repo = FirestoreRepo(settings.project) if settings.repo_backend == "firestore" else InMemoryRepo()
    if settings.gemini_backend == "vertex":
        gemini = RateLimitedGemini(VertexGemini(settings), SlidingWindowLimiter(settings.gemini_rpm, 60),
                                   daily=DailyCap(repo, settings.gemini_daily_cap))
    else:
        gemini = StubGemini()
    verifier = FirebaseVerifier(settings.project) if settings.auth_backend == "firebase" else StubVerifier()
    return Services(settings=settings, repo=repo, gemini=gemini, verifier=verifier,
                    assessments=AssessmentService(repo, gemini, settings, clock=clock))


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    services = services or build_services(settings or load_settings())
    settings = services.settings
    app = FastAPI(title="KasFlow Client API", version="1.0.0", description=API_DESCRIPTION)
    app.state.services = services

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {
            "code": "validation_error", "message": "Request validation failed",
            "details": jsonable_encoder(exc.errors(), custom_encoder={Exception: str})}})

    app.include_router(client_api.router)
    app.include_router(console_api.router)
    app.include_router(collect_api.router)
    app.include_router(demo.router)
    app.include_router(pages.router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"ok": True}

    @app.get("/config.js", include_in_schema=False)
    def config_js():
        cfg = {"authMode": settings.auth_backend, "firebase": settings.firebase_web}
        return Response(f"window.KASFLOW_CONFIG = {json.dumps(cfg)};", media_type="application/javascript",
                        headers={"Cache-Control": "no-store"})

    seeding.ensure_demo_client(services.repo, settings)
    if settings.seed_on_start:
        seeding.seed(services.repo, services.assessments, settings)
    return app


app = create_app()
