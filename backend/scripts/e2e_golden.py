#!/usr/bin/env python
"""E2E golden path — the mock-first acceptance test for the whole product flow.

Drives the whole product flow through the in-process app (TestClient) with the
MOCK image lanes enabled (so sketches are generated and the moodboard is truly
hybrid), then asserts the editable handoff is complete: provenance-complete
sketches, a mixed-provenance moodboard, valid design tokens, and an export.md
with the required sections. Exits 0 on success, 1 on failure.

Run via ``make e2e``. Uses only mocks — no API keys, no network.
"""

from __future__ import annotations

import os
import sys

# Mock-first, but with both image lanes ON so the golden path exercises real
# generated + sourced provenance. Clear any real keys so nothing hits a network.
os.environ["APP_DISABLE_DOTENV"] = "1"
os.environ["IMAGE_GEN_PROVIDER"] = "mock"
os.environ["IMAGE_SOURCE_PROVIDER"] = "pexels"
for _key in ("ANTHROPIC_API_KEY", "IDEATOR_BASE_URL", "IDEATOR_API_KEY", "TAVILY_API_KEY"):
    os.environ.pop(_key, None)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

BRIEF = {
    "brief": "Launch a sustainable sneaker brand for runners who are sick of greenwashing.",
    "audience": "runners frustrated by greenwashing",
}


def _post(client, path, **json):
    r = client.post(path, json=json or None)
    assert r.status_code in (200, 202), f"POST {path} -> {r.status_code}: {r.text}"
    return r


def main() -> int:
    with TestClient(app) as client:
        pid = client.post("/api/projects", json=BRIEF).json()["id"]
        _post(client, f"/api/projects/{pid}/start")
        assert client.get(f"/api/projects/{pid}").json()["state"] == "awaiting_strategy_approval"

        # Gate 1 approve -> fan out -> Gate 2
        _post(client, f"/api/projects/{pid}/gates/strategy", action="approve")
        view = client.get(f"/api/projects/{pid}").json()
        assert view["state"] == "awaiting_curation", view["state"]
        ids = [d["id"] for d in view["directions"]]
        assert len(ids) >= 3, f"expected >=3 directions, got {len(ids)}"

        # exercise the full curation surface
        _post(client, f"/api/projects/{pid}/directions/{ids[0]}/regenerate_sketch", index=0)
        _post(client, f"/api/projects/{pid}/directions/{ids[1]}/regenerate_sketches")
        _post(client, f"/api/projects/{pid}/directions/{ids[0]}/regenerate_moodboard_item", index=0, kind="sourced")
        _post(client, f"/api/projects/{pid}/directions/{ids[2]}/edit", field="copy.headline", value="Nothing to hide.")
        _post(client, f"/api/projects/{pid}/directions/{ids[-1]}/kill")  # kill the weakest
        merged_view = _post(
            client, f"/api/projects/{pid}/directions/merge", direction_ids=[ids[0], ids[1]], field_choices={"big_idea": ids[0]}
        ).json()
        merged_id = next(d["id"] for d in merged_view["directions"] if d.get("merged_from"))
        _post(client, f"/api/projects/{pid}/directions/{ids[2]}/fork", lens_tweak="louder and angrier")
        _post(client, f"/api/projects/{pid}/directions/{merged_id}/recritique")
        _post(client, f"/api/projects/{pid}/directions/{merged_id}/promote")
        _post(client, f"/api/projects/{pid}/finalize", refine=True)

        # ---- assert the editable handoff is complete ----
        assert client.get(f"/api/projects/{pid}").json()["state"] == "done"
        packages = client.get(f"/api/projects/{pid}/packages").json()
        assert packages, "no packages produced"
        pkg = packages[0]

        assert pkg["sketches"], "package has no sketches"
        assert all(s["kind"] != "sourced" for s in pkg["sketches"]), "sketches must never be sourced"
        assert all(
            (s["kind"] == "generated" and s["gen_model"] and s["gen_prompt"]) or s["kind"] == "placeholder"
            for s in pkg["sketches"]
        ), "sketch provenance incomplete"

        moodboard = pkg["art_direction"]["moodboard"]
        kinds = {m["kind"] for m in moodboard}
        assert {"generated", "sourced"} <= kinds, f"moodboard not mixed-provenance: {kinds}"

        tokens_json = client.get(f"/api/projects/{pid}/tokens.json").json()
        assert tokens_json.get("color"), "no color tokens"
        assert ":root {" in client.get(f"/api/projects/{pid}/tokens.css").text

        md = client.get(f"/api/projects/{pid}/export.md").text
        for section in ("### Sketches", "## Assets & licensing", "## AI disclosure"):
            assert section in md, f"export.md missing {section!r}"
        assert "AI-generated via" in md and "©" in md, "export.md missing per-kind provenance lines"

        print(f"E2E OK: project {pid} finalized; {len(packages)} package(s); moodboard kinds {sorted(kinds)}")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"E2E FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
