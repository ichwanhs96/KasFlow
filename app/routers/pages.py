from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import STATIC_DIR

router = APIRouter(include_in_schema=False)
NO_CACHE = {"Cache-Control": "no-cache"}


def _page(name: str, extra: dict | None = None) -> FileResponse:
    return FileResponse(STATIC_DIR / name, media_type="text/html", headers={**NO_CACHE, **(extra or {})})


@router.get("/")
def index():
    return _page("index.html")


@router.get("/console")
def console():
    return _page("console.html")


@router.get("/c/{token}")
def collect(token: str):
    return _page("collect.html", {"Content-Security-Policy": "frame-ancestors *"})


@router.get("/demo/client")
def demo_client():
    return _page("demo/client.html")


@router.get("/demo/intro")
def demo_intro():
    return _page("demo/intro.html")


@router.get("/demo/outro")
def demo_outro():
    return _page("demo/outro.html")


@router.get("/demo-login")
def demo_login():
    return _page("demo/login.html")
