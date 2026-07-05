#!/usr/bin/env python
"""Dev seed (Stage 09) — seed one project paused at Gate 2 (curation) into the
durable stores, so ``make dev-backend`` + the UI open straight into a populated
Cockpit for demos and manual QA.

Mock-first: forces the mock model + image lanes and clears every provider key, so
it seeds with NO API keys and NO network. Writes to the same ``data/`` directory
the dev server reads (registry + checkpoint + generated placeholder images), so a
freshly started backend process sees the project waiting at the curation gate.

Run via ``make demo``.
"""

from __future__ import annotations

import os
import sys

# Mock-first, both image lanes on (hybrid moodboard), no dotenv, no real keys.
os.environ.setdefault("APP_DISABLE_DOTENV", "1")
os.environ.setdefault("IMAGE_GEN_PROVIDER", "mock")
os.environ.setdefault("IMAGE_SOURCE_PROVIDER", "pexels")
for _key in ("ANTHROPIC_API_KEY", "CONCEPTIAL_BASE_URL", "CONCEPTIAL_API_KEY", "TAVILY_API_KEY"):
    os.environ.pop(_key, None)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

BRIEF = {
    "brief": "Launch a sustainable sneaker brand for runners who are sick of greenwashing.",
    "audience": "runners frustrated by greenwashing",
    "constraints": ["No greenwashing clichés", "Feel earned, not preachy"],
}


def main() -> int:
    # TestClient drives the real app lifespan, so this persists to data/ exactly
    # as a live server would.
    with TestClient(app) as client:
        pid = client.post("/api/projects", json=BRIEF).json()["id"]
        client.post(f"/api/projects/{pid}/start")
        client.post(f"/api/projects/{pid}/gates/strategy", json={"action": "approve"})
        view = client.get(f"/api/projects/{pid}").json()
        state, directions = view["state"], view.get("directions", [])

    if state != "awaiting_curation":
        print(f"SEED FAILED: expected awaiting_curation, got {state!r}", file=sys.stderr)
        return 1

    print(f"Seeded project {pid} at Gate 2 (curation) with {len(directions)} directions.")
    print("Next:")
    print("  make dev-backend        # in one shell")
    print("  make dev-frontend       # in another; open the project in the Studio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
