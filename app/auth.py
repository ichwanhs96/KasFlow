from typing import Protocol

from app.config import DEMO_ANALYST_EMAIL
from app.errors import AppError
from app.models import Analyst


class Verifier(Protocol):
    def verify(self, token: str) -> Analyst: ...
    def mint_demo(self) -> dict: ...


class StubVerifier:
    """Local/dev auth: accepts tokens of the form 'stub:<email>'."""

    def verify(self, token: str) -> Analyst:
        if not token or not token.startswith("stub:") or len(token) < 6:
            raise AppError(401, "unauthorized", "Invalid token")
        email = token[5:]
        return Analyst(uid=f"stub-{email}", email=email)

    def mint_demo(self) -> dict:
        return {"mode": "stub", "token": f"stub:{DEMO_ANALYST_EMAIL}"}


class FirebaseVerifier:
    """Firebase Auth. Provider check is unit-tested with a monkeypatch; verified live in Phase B."""

    def __init__(self, project: str) -> None:
        import firebase_admin

        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={"projectId": project} if project else None)

    def verify(self, token: str) -> Analyst:
        from firebase_admin import auth

        try:
            decoded = auth.verify_id_token(token)
        except Exception as e:  # noqa: BLE001
            raise AppError(401, "unauthorized", "Invalid token") from e
        provider = (decoded.get("firebase") or {}).get("sign_in_provider")
        if provider not in ("google.com", "custom"):
            raise AppError(403, "forbidden", "Unsupported sign-in provider")
        return Analyst(uid=decoded["uid"], email=decoded.get("email") or DEMO_ANALYST_EMAIL)

    def mint_demo(self) -> dict:
        from firebase_admin import auth

        token = auth.create_custom_token("demo-analyst", {"email": DEMO_ANALYST_EMAIL})
        return {"mode": "firebase", "token": token.decode() if isinstance(token, bytes) else token}
