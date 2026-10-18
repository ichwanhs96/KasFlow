from datetime import timedelta

from app.models import Collection
from app.repo import InMemoryRepo
from app.services.tokens import collection_url, hash_secret, new_collection_token
from tests.factories import T0, assessment, tx


def test_collection_token_is_random_and_hashed():
    raw1, h1 = new_collection_token()
    raw2, _ = new_collection_token()
    assert raw1 != raw2 and len(raw1) >= 40
    assert h1 == hash_secret(raw1) and len(h1) == 64 and raw1 not in h1


def test_collection_url_format():
    assert collection_url("https://x.web.app/", "abc") == "https://x.web.app/c/abc"


def test_inmemory_repo_roundtrip_and_isolation():
    repo = InMemoryRepo()
    a = assessment()
    repo.create_assessment(a)
    got = repo.get_assessment(a.id)
    got.purpose = "changed"
    assert repo.get_assessment(a.id).purpose == "loan"  # stored copy is isolated
    got.collection = Collection(token_hash="h1", created_at=T0, expires_at=T0 + timedelta(hours=72))
    repo.save_assessment(got)
    assert repo.find_by_token_hash("h1").id == a.id
    assert repo.find_by_token_hash("nope") is None
    repo.put_transactions(a.id, [tx("2026-09-01", 100)])
    assert len(repo.get_transactions(a.id)) == 1
    assert [x.id for x in repo.list_assessments("c1")] == [a.id]
    assert repo.list_assessments("other") == []
    repo.delete_assessment(a.id)
    assert repo.get_assessment(a.id) is None and repo.get_transactions(a.id) == []


def test_inmemory_clients():
    repo = InMemoryRepo()
    repo.put_client("pc", {"name": "PinjamCepat", "api_key_hash": hash_secret("k")})
    assert repo.get_client_by_key_hash(hash_secret("k"))["id"] == "pc"
    assert repo.get_client_by_key_hash(hash_secret("x")) is None
    assert repo.get_client("pc")["name"] == "PinjamCepat"
