from datetime import datetime, timezone

import pytest

from app import seeding
from app.config import ASSETS_DIR, Settings, load_settings
from app.errors import AppError
from app.repo import InMemoryRepo
from app.services.gemini import GeminiError, GeminiRateLimited, RateLimitedGemini, StubGemini
from app.services.pipeline import AssessmentService
from app.services.ratelimit import SlidingWindowLimiter

NOW = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)


class Mono:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_limiter_allows_n_per_window_then_recovers():
    mono = Mono()
    lim = SlidingWindowLimiter(5, 60, clock=mono)
    assert all(lim.try_acquire() for _ in range(5))
    assert not lim.try_acquire()
    mono.t += 59.9
    assert not lim.try_acquire()
    mono.t += 0.2
    assert lim.try_acquire()


def test_settings_default_to_five_gemini_calls_per_minute(monkeypatch):
    monkeypatch.delenv("GEMINI_RPM", raising=False)
    assert Settings().gemini_rpm == 5 and load_settings().gemini_rpm == 5
    monkeypatch.setenv("GEMINI_RPM", "12")
    assert load_settings().gemini_rpm == 12


def limited_service(rpm, mono):
    repo = InMemoryRepo()
    seeding.ensure_demo_client(repo, Settings())
    gem = RateLimitedGemini(StubGemini(), SlidingWindowLimiter(rpm, 60, clock=mono))
    return AssessmentService(repo, gem, Settings(), clock=lambda: NOW), repo


def test_rate_limited_gemini_raises_typed_error():
    mono = Mono()
    g = RateLimitedGemini(StubGemini(), SlidingWindowLimiter(1, 60, clock=mono))
    g.summarize({"metrics": {}}, purpose="loan", language="en")
    with pytest.raises(GeminiRateLimited) as e:
        g.summarize({"metrics": {}}, purpose="loan", language="en")
    assert isinstance(e.value, GeminiError)


def test_upload_over_limit_returns_429_and_does_not_use_up_an_item():
    svc, repo = limited_service(1, Mono())
    a, url = svc.create("pinjamcepat", seeding.build_request(seeding.load_profile("sari"), "RL-1"))
    token = url.rsplit("/c/", 1)[1]
    data = (ASSETS_DIR / "sari_dompetku.png").read_bytes()
    assert svc.add_item(token, data=data, filename="sari_dompetku.png", mime_type="image/png", kind="upload").status == "done"
    with pytest.raises(AppError) as e:
        svc.add_item(token, data=data, filename="sari_dompetku.png", mime_type="image/png", kind="upload")
    assert e.value.status == 429 and e.value.code == "rate_limited"
    assert len(repo.get_assessment(a.id).collection.items) == 1


def test_summary_over_limit_still_scores_and_can_be_regenerated():
    mono = Mono()
    svc, _ = limited_service(0, mono)
    a, _ = svc.create("pinjamcepat", seeding.build_request(seeding.load_profile("paolo"), "RL-2"))
    assert a.status == "scored" and a.result.ai_summary is None
    assert "summary_failed" in [e.type for e in a.events]


def test_collect_api_maps_rate_limit_to_429(client, services):
    services.assessments.gemini = RateLimitedGemini(StubGemini(), SlidingWindowLimiter(0, 60, clock=Mono()))
    _, url = services.assessments.create("pinjamcepat", seeding.build_request(seeding.load_profile("sari"), "RL-3"))
    token = url.rsplit("/c/", 1)[1]
    with open(ASSETS_DIR / "sari_dompetku.png", "rb") as f:
        r = client.post(f"/api/collect/{token}/items", files={"file": ("sari_dompetku.png", f, "image/png")})
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"


def test_build_services_rate_limits_only_live_gemini(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "VertexGemini", lambda settings: StubGemini())
    live = main.build_services(Settings(gemini_backend="vertex", gemini_rpm=5))
    assert isinstance(live.gemini, RateLimitedGemini) and live.gemini.limiter.limit == 5
    assert live.assessments.gemini is live.gemini
    assert isinstance(main.build_services(Settings()).gemini, StubGemini)


# ---- daily cap (persisted, so it survives scale-to-zero restarts) ----
from datetime import timedelta  # noqa: E402

from app.services.gemini import GeminiDailyLimit  # noqa: E402
from app.services.ratelimit import DailyCap  # noqa: E402


class Day:
    def __init__(self):
        self.now = datetime(2026, 10, 18, 23, 59, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


def test_inmemory_daily_counter_is_capped_per_key():
    repo = InMemoryRepo()
    assert [repo.incr_daily_counter("gemini-2026-10-18", 2) for _ in range(3)] == [True, True, False]
    assert repo.incr_daily_counter("gemini-2026-10-19", 2) is True


def test_daily_cap_resets_at_utc_midnight():
    day = Day()
    cap = DailyCap(InMemoryRepo(), 2, clock=day)
    assert cap.try_acquire() and cap.try_acquire() and not cap.try_acquire()
    day.now += timedelta(minutes=2)
    assert cap.try_acquire()


def test_settings_default_daily_cap_is_150(monkeypatch):
    monkeypatch.delenv("GEMINI_DAILY_CAP", raising=False)
    assert Settings().gemini_daily_cap == 150 and load_settings().gemini_daily_cap == 150
    monkeypatch.setenv("GEMINI_DAILY_CAP", "40")
    assert load_settings().gemini_daily_cap == 40


def test_daily_limit_is_its_own_error_and_checked_after_the_minute_limit():
    mono = Mono()
    day_cap = DailyCap(InMemoryRepo(), 1, clock=Day())
    g = RateLimitedGemini(StubGemini(), SlidingWindowLimiter(5, 60, clock=mono), daily=day_cap)
    g.summarize({"metrics": {}}, purpose="loan", language="en")
    with pytest.raises(GeminiDailyLimit) as e:
        g.summarize({"metrics": {}}, purpose="loan", language="en")
    assert isinstance(e.value, GeminiRateLimited)
    minute_only = RateLimitedGemini(StubGemini(), SlidingWindowLimiter(0, 60, clock=mono), daily=DailyCap(InMemoryRepo(), 9, clock=Day()))
    with pytest.raises(GeminiRateLimited):
        minute_only.summarize({}, purpose="loan", language="en")
    assert minute_only.daily.repo.counters == {}  # a minute-limited call doesn't spend the daily budget


def test_upload_over_daily_cap_returns_429_daily_limit():
    repo = InMemoryRepo()
    seeding.ensure_demo_client(repo, Settings())
    gem = RateLimitedGemini(StubGemini(), SlidingWindowLimiter(9, 60, clock=Mono()), daily=DailyCap(repo, 0, clock=Day()))
    svc = AssessmentService(repo, gem, Settings(), clock=lambda: NOW)
    _, url = svc.create("pinjamcepat", seeding.build_request(seeding.load_profile("sari"), "DC-1"))
    with pytest.raises(AppError) as e:
        svc.add_item(url.rsplit("/c/", 1)[1], data=(ASSETS_DIR / "sari_dompetku.png").read_bytes(),
                     filename="sari_dompetku.png", mime_type="image/png", kind="upload")
    assert e.value.status == 429 and e.value.code == "daily_limit_reached"


def test_build_services_wires_the_daily_cap(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "VertexGemini", lambda settings: StubGemini())
    live = main.build_services(Settings(gemini_backend="vertex", gemini_daily_cap=150))
    assert live.gemini.daily.limit == 150 and live.gemini.daily.repo is live.repo
