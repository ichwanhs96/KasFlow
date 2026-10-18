#!/usr/bin/env python3
"""Phase B: seed the demo client + Paolo/Linh into Firestore.

Extraction uses stub fixtures (deterministic); summaries use live Gemini unless --no-ai.
Env: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GEMINI_MODEL, DEMO_CLIENT_API_KEY, PUBLIC_BASE_URL.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import seeding  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.repo import FirestoreRepo  # noqa: E402
from app.services.gemini import GeminiError, StubGemini, VertexGemini  # noqa: E402
from app.services.pipeline import AssessmentService  # noqa: E402


class SeedGemini(StubGemini):
    def __init__(self, live):
        super().__init__()
        self.live = live

    def summarize(self, facts, *, purpose, language):
        if self.live is None:
            raise GeminiError("--no-ai")
        return self.live.summarize(facts, purpose=purpose, language=language)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-ai", action="store_true")
    args = ap.parse_args()
    settings = load_settings()
    repo = FirestoreRepo(settings.project)
    gemini = SeedGemini(None if args.no_ai else VertexGemini(settings))
    service = AssessmentService(repo, gemini, settings)
    for a in seeding.seed(repo, service, settings):
        print(f"seeded {a.external_ref}: {a.status} {a.result.grade if a.result else '-'}")


if __name__ == "__main__":
    main()
