from __future__ import annotations

from typing import Protocol

from app.models import Assessment, Transaction, utcnow


class Repo(Protocol):
    def get_client_by_key_hash(self, h: str) -> dict | None: ...
    def get_client(self, client_id: str) -> dict | None: ...
    def put_client(self, client_id: str, data: dict) -> None: ...
    def create_assessment(self, a: Assessment) -> None: ...
    def get_assessment(self, id: str) -> Assessment | None: ...
    def save_assessment(self, a: Assessment) -> None: ...
    def list_assessments(self, client_id: str | None = None) -> list[Assessment]: ...
    def find_by_token_hash(self, h: str) -> Assessment | None: ...
    def get_transactions(self, id: str) -> list[Transaction]: ...
    def put_transactions(self, id: str, txns: list[Transaction]) -> None: ...
    def delete_assessment(self, id: str) -> None: ...
    def incr_daily_counter(self, key: str, limit: int) -> bool: ...


class InMemoryRepo:
    def __init__(self) -> None:
        self.clients: dict[str, dict] = {}
        self.assessments: dict[str, Assessment] = {}
        self.txns: dict[str, list[Transaction]] = {}
        self.counters: dict[str, int] = {}

    def get_client_by_key_hash(self, h):
        for cid, c in self.clients.items():
            if c.get("api_key_hash") == h:
                return dict(c, id=cid)
        return None

    def get_client(self, client_id):
        c = self.clients.get(client_id)
        return dict(c, id=client_id) if c else None

    def put_client(self, client_id, data):
        self.clients[client_id] = dict(data)

    def create_assessment(self, a):
        self.assessments[a.id] = a.model_copy(deep=True)

    def get_assessment(self, id):
        a = self.assessments.get(id)
        return a.model_copy(deep=True) if a else None

    def save_assessment(self, a):
        a.updated_at = utcnow()
        self.assessments[a.id] = a.model_copy(deep=True)

    def list_assessments(self, client_id=None):
        return [a.model_copy(deep=True) for a in self.assessments.values()
                if client_id is None or a.client_id == client_id]

    def find_by_token_hash(self, h):
        for a in self.assessments.values():
            if a.collection and a.collection.token_hash == h:
                return a.model_copy(deep=True)
        return None

    def get_transactions(self, id):
        return [t.model_copy() for t in self.txns.get(id, [])]

    def put_transactions(self, id, txns):
        self.txns[id] = [t.model_copy() for t in txns]

    def delete_assessment(self, id):
        self.assessments.pop(id, None)
        self.txns.pop(id, None)

    def incr_daily_counter(self, key, limit):
        if self.counters.get(key, 0) >= limit:
            return False
        self.counters[key] = self.counters.get(key, 0) + 1
        return True


class FirestoreRepo:
    """Firestore implementation. Not exercised by tests (same contract as InMemoryRepo); verified against live Firestore."""

    def __init__(self, project: str) -> None:
        from google.cloud import firestore

        self._db = firestore.Client(project=project or None)

    def _a(self):
        return self._db.collection("assessments")

    def _where(self, coll, field, value):
        from google.cloud.firestore_v1.base_query import FieldFilter

        return coll.where(filter=FieldFilter(field, "==", value))

    def get_client_by_key_hash(self, h):
        docs = list(self._where(self._db.collection("clients"), "api_key_hash", h).limit(1).stream())
        return dict(docs[0].to_dict(), id=docs[0].id) if docs else None

    def get_client(self, client_id):
        d = self._db.collection("clients").document(client_id).get()
        return dict(d.to_dict(), id=d.id) if d.exists else None

    def put_client(self, client_id, data):
        self._db.collection("clients").document(client_id).set(data)

    def create_assessment(self, a):
        self._a().document(a.id).set(a.model_dump(mode="json"))

    def get_assessment(self, id):
        d = self._a().document(id).get()
        return Assessment.model_validate(d.to_dict()) if d.exists else None

    def save_assessment(self, a):
        a.updated_at = utcnow()
        self._a().document(a.id).set(a.model_dump(mode="json"))

    def list_assessments(self, client_id=None):
        q = self._where(self._a(), "client_id", client_id) if client_id else self._a()
        return [Assessment.model_validate(d.to_dict()) for d in q.stream()]

    def find_by_token_hash(self, h):
        docs = list(self._where(self._a(), "collection.token_hash", h).limit(1).stream())
        return Assessment.model_validate(docs[0].to_dict()) if docs else None

    def get_transactions(self, id):
        d = self._db.collection("assessment_transactions").document(id).get()
        if not d.exists:
            return []
        return [Transaction.model_validate(x) for x in d.to_dict().get("transactions", [])]

    def put_transactions(self, id, txns):
        self._db.collection("assessment_transactions").document(id).set(
            {"transactions": [t.model_dump(mode="json") for t in txns]})

    def delete_assessment(self, id):
        self._a().document(id).delete()
        self._db.collection("assessment_transactions").document(id).delete()

    def incr_daily_counter(self, key, limit):
        """Atomically take one unit from a capped counter (collection `usage`). False once the cap is reached."""
        from google.cloud import firestore

        ref = self._db.collection("usage").document(key)

        @firestore.transactional
        def take(txn):
            snap = ref.get(transaction=txn)
            count = (snap.to_dict() or {}).get("count", 0) if snap.exists else 0
            if count >= limit:
                return False
            txn.set(ref, {"count": count + 1, "limit": limit, "updated_at": firestore.SERVER_TIMESTAMP})
            return True

        return take(self._db.transaction())
