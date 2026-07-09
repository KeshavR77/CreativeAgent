"""The three ideation modes (§ideation): internal pass-through, manual
external-brainstorm gate with in-house critique, and the automatic
brainstorm⇄critique loop. Keyless-first: everything runs on the mock."""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.models.artifacts import IdeaReview, Territory
from app.services.ideation import best_idea_per_territory, parse_external_ideas

BRIEF_BODY = {
    "brief": "Launch a sustainable sneaker brand for urban runners.",
    "audience": "urban runners",
}


@pytest.fixture
def client(clean_env):
    with TestClient(app) as c:
        yield c


def _to_gate1(client, mode: str) -> str:
    r = client.post("/api/projects", json={**BRIEF_BODY, "ideation_mode": mode})
    assert r.status_code == 201, r.text
    assert r.json()["ideation_mode"] == mode
    pid = r.json()["id"]
    assert client.post(f"/api/projects/{pid}/start").status_code == 202
    assert client.get(f"/api/projects/{pid}").json()["state"] == "awaiting_strategy_approval"
    return pid


def _approve_strategy(client, pid: str) -> dict:
    r = client.post(f"/api/projects/{pid}/gates/strategy", json={"action": "approve"})
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------- #
# parsing / selection units                                                    #
# --------------------------------------------------------------------------- #
def _territories() -> list[Territory]:
    return [
        Territory(label="Radical Proof", lens="evidence"),
        Territory(label="Quiet Rebellion", lens="tone"),
    ]


def test_parse_documented_format_matches_casefold(clean_env) -> None:
    text = "### radical proof\nPublish the audit.\n\n### Quiet Rebellion\nSay less, show more."
    ideas = parse_external_ideas(text, _territories())
    assert {(i.territory_label, i.big_idea) for i in ideas} == {
        ("Radical Proof", "Publish the audit."),
        ("Quiet Rebellion", "Say less, show more."),
    }


def test_parse_unmatched_headings_fill_uncovered_territories_in_order(clean_env) -> None:
    text = "### Something Else\nAn orphan idea."
    ideas = parse_external_ideas(text, _territories())
    assert len(ideas) == 1
    assert ideas[0].territory_label == "Radical Proof"  # first uncovered territory


def test_parse_multiple_ideas_per_territory_kept(clean_env) -> None:
    text = "### Radical Proof\nIdea one.\n\n### Radical Proof\nIdea two."
    ideas = parse_external_ideas(text, _territories())
    assert [i.big_idea for i in ideas] == ["Idea one.", "Idea two."]


def test_parse_freeform_falls_back_to_llm_parse(clean_env) -> None:
    # No headings at all -> the LLM (mock) parse path; must not crash and must
    # return a list (mock output is schema-valid but content-arbitrary).
    ideas = parse_external_ideas("just a wall of text with ideas buried in it", _territories())
    assert isinstance(ideas, list)


def test_best_idea_per_territory_picks_highest_score(clean_env) -> None:
    reviews = [
        IdeaReview(territory_label="A", big_idea="weak", score=2.0),
        IdeaReview(territory_label="A", big_idea="strong", score=4.5),
        IdeaReview(territory_label="B", big_idea="only", score=0.0),
    ]
    best = best_idea_per_territory(reviews)
    assert best == {"A": "strong", "B": "only"}


# --------------------------------------------------------------------------- #
# mode: internal (default) — gate is a pass-through                            #
# --------------------------------------------------------------------------- #
def test_internal_mode_runs_straight_to_curation(client) -> None:
    pid = _to_gate1(client, "internal")
    view = _approve_strategy(client, pid)
    assert view["state"] == "awaiting_curation"
    assert view["ideation_mode"] == "internal"
    assert view["directions"], "explore fan-out produced directions"


# --------------------------------------------------------------------------- #
# mode: manual — pause, packet, submit (critique), proceed                     #
# --------------------------------------------------------------------------- #
def test_manual_mode_gate_flow(client) -> None:
    pid = _to_gate1(client, "manual")
    view = _approve_strategy(client, pid)
    assert view["state"] == "awaiting_ideation"
    territories = [t["label"] for t in view["territories"]]
    assert territories

    # packet downloads and carries the territory headings + return format
    r = client.get(f"/api/projects/{pid}/ideation-packet.md")
    assert r.status_code == 200
    packet = r.text
    for label in territories:
        assert f"### {label}" in packet
    assert "What to return" in packet

    # submit external ideas -> critiqued, still at the gate (iterate loop)
    ideas_text = "\n\n".join(f"### {label}\nBig idea for {label}." for label in territories)
    r = client.post(
        f"/api/projects/{pid}/gates/ideation",
        json={"action": "submit", "ideas_text": ideas_text},
    )
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["state"] == "awaiting_ideation"
    reviews = (view["interrupt"] or {}).get("reviews") or []
    assert len(reviews) == len(territories)
    assert all(r["score"] > 0 for r in reviews), "each idea was critiqued"
    assert all(r["case_against"] for r in reviews)

    # proceed -> explore consumes the external ideas verbatim, brain=external
    r = client.post(f"/api/projects/{pid}/gates/ideation", json={"action": "proceed"})
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["state"] == "awaiting_curation"
    by_label = {d["territory"]["label"]: d for d in view["directions"]}
    for label in territories:
        assert by_label[label]["brain"] == "external"
        assert by_label[label]["big_idea"] == f"Big idea for {label}."


def test_manual_gate_endpoint_guards(client) -> None:
    pid = _to_gate1(client, "manual")
    # not at the ideation gate yet -> 409
    r = client.post(f"/api/projects/{pid}/gates/ideation", json={"action": "proceed"})
    assert r.status_code == 409
    _approve_strategy(client, pid)
    # bad action -> 422; empty submit -> 422
    assert (
        client.post(f"/api/projects/{pid}/gates/ideation", json={"action": "nope"}).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/projects/{pid}/gates/ideation", json={"action": "submit", "ideas_text": "  "}
        ).status_code
        == 422
    )


def test_manual_proceed_without_ideas_falls_back_to_internal_ideation(client) -> None:
    pid = _to_gate1(client, "manual")
    view = _approve_strategy(client, pid)
    assert view["state"] == "awaiting_ideation"
    r = client.post(f"/api/projects/{pid}/gates/ideation", json={"action": "proceed"})
    view = r.json()
    assert view["state"] == "awaiting_curation"
    assert view["directions"]
    assert all(d["brain"] != "external" for d in view["directions"])


# --------------------------------------------------------------------------- #
# mode: conceptial — automatic brainstorm⇄critique loop                        #
# --------------------------------------------------------------------------- #
def test_conceptial_mode_loops_brainstorm_and_critique(client, monkeypatch) -> None:
    # The mock idea critique scores 3.2 (< bar), so the loop regenerates once per
    # territory: ideator calls == 2 × territories.
    from app.graph import exploration

    calls = {"n": 0}
    real_ideate = exploration.ideate_one

    def counting_ideate(project_id, territory, *, lens_tweak=None):
        calls["n"] += 1
        return real_ideate(project_id, territory, lens_tweak=lens_tweak)

    monkeypatch.setattr(exploration, "ideate_one", counting_ideate)

    pid = _to_gate1(client, "conceptial")
    view = _approve_strategy(client, pid)
    assert view["state"] == "awaiting_curation"
    n_dirs = len(view["directions"])
    assert n_dirs >= 2
    assert calls["n"] == 2 * n_dirs, "each territory brainstormed, critiqued, regenerated once"


def test_ideate_iterative_stops_early_on_strong_idea(clean_env, monkeypatch) -> None:
    from app.graph import exploration
    from app.services import ideation

    monkeypatch.setattr(
        exploration, "ideate_one", lambda pid, t, *, lens_tweak=None: ("great idea", "mock")
    )
    monkeypatch.setattr(
        ideation,
        "critique_idea",
        lambda pid, label, idea, strategy=None: ideation.IdeaCritiqueResult(score=4.8),
    )
    idea, brain = exploration.ideate_iterative("p", Territory(label="T", lens="l"))
    assert idea == "great idea" and brain == "mock"


def test_invalid_mode_rejected_at_create(client) -> None:
    r = client.post("/api/projects", json={**BRIEF_BODY, "ideation_mode": "telepathy"})
    assert r.status_code == 422
