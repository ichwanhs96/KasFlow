import hashlib
import secrets


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_collection_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_secret(raw)


def collection_url(base: str, raw: str) -> str:
    return f"{base.rstrip('/')}/c/{raw}"
