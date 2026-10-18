"""The billing shutoff function (local-only infra; skipped on a clean clone)."""
import base64
import importlib.util
import json

import pytest

from app.config import ROOT

SRC = ROOT / "infra" / "billing_cap" / "main.py"
if not SRC.exists():
    pytest.skip("infra/billing_cap is local-only (gitignored)", allow_module_level=True)
spec = importlib.util.spec_from_file_location("billing_cap", SRC)
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)


class FakeSession:
    def __init__(self, billing_enabled=True):
        self.calls = []
        self.billing_enabled = billing_enabled

    def get(self, url):
        self.calls.append(("GET", url, None))
        return FakeResp({"billingEnabled": self.billing_enabled})

    def put(self, url, json=None):
        self.calls.append(("PUT", url, json))
        return FakeResp({})


class FakeResp:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def msg(cost, budget):
    return {"costAmount": cost, "budgetAmount": budget, "budgetDisplayName": "kasflow", "currencyCode": "USD"}


def test_under_budget_does_nothing():
    s = FakeSession()
    assert cap.handle(msg(9.99, 10), project="p1", session=s) == "under budget"
    assert s.calls == []


def test_at_budget_unlinks_billing():
    s = FakeSession()
    assert cap.handle(msg(10.0, 10), project="p1", session=s) == "billing disabled"
    assert s.calls[-1] == ("PUT", "https://cloudbilling.googleapis.com/v1/projects/p1/billingInfo",
                           {"billingAccountName": ""})


def test_already_disabled_is_a_no_op():
    s = FakeSession(billing_enabled=False)
    assert cap.handle(msg(25, 10), project="p1", session=s) == "already disabled"
    assert [c[0] for c in s.calls] == ["GET"]


def test_decodes_pubsub_cloud_event():
    data = base64.b64encode(json.dumps(msg(1, 10)).encode()).decode()
    assert cap.decode({"message": {"data": data}}) == msg(1, 10)
