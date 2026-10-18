import json

from fastapi import FastAPI, Response

from app.config import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="KasFlow Client API", version="1.0.0")

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"ok": True}

    @app.get("/config.js", include_in_schema=False)
    def config_js():
        cfg = {"authMode": settings.auth_backend, "firebase": settings.firebase_web}
        return Response(f"window.KASFLOW_CONFIG = {json.dumps(cfg)};", media_type="application/javascript")

    return app


app = create_app()
