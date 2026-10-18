from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import build_services, create_app

FIXED_NOW = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now=FIXED_NOW):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def services(clock):
    return build_services(Settings(), clock=clock)


@pytest.fixture
def client(services):
    return TestClient(create_app(services=services))
