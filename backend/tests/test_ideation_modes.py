"""The three ideation modes: internal pass-through, manual
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
# mode: auto — brainstorm (spark) ⇄ develop ⇄ critique loop                     #
# --------------------------------------------------------------------------- #
def test_auto_mode_end_to_end_keyless(client) -> None:
    # Keyless: no external ideator, so ideate_one returns a mock seed
    # (brain="mock") and ideate_iterative uses it as-is (no develop). The run
    # still reaches curation with critiqued directions — the mode wires up
    # end to end.
    pid = _to_gate1(client, "auto")
    view = _approve_strategy(client, pid)
    assert view["state"] == "awaiting_curation"
    assert len(view["directions"]) >= 2
    assert all(d["critique"] for d in view["directions"])


def test_ideator_seed_is_developed_then_critique_loops(clean_env, monkeypatch) -> None:
    # With a REAL external-ideator spark (brain="external_ideator"), the seed is developed by
    # the reasoning model, critiqued, and resparked+redeveloped once when weak.
    from app.graph import exploration
    from app.services import ideation

    sparks = {"n": 0}
    develops = {"n": 0}

    def fake_spark(pid, t, *, lens_tweak=None, brief_context=""):
        sparks["n"] += 1
        return f"raw spark {sparks['n']}", "external_ideator"

    def fake_develop(pid, t, seed, ctx):
        develops["n"] += 1
        return f"developed({seed})"

    monkeypatch.setattr(exploration, "ideate_one", fake_spark)
    monkeypatch.setattr(exploration, "_develop_seed", fake_develop)
    # First critique weak (< bar) -> loop; the loop's post-develop idea isn't re-critiqued.
    monkeypatch.setattr(
        ideation, "critique_idea", lambda pid, label, idea, strategy=None: ideation.IdeaCritiqueResult(score=2.5)
    )
    idea, brain = exploration.ideate_iterative("p", Territory(label="T", lens="l"), brief_context="ctx")
    assert brain == "external_ideator+glm"
    assert sparks["n"] == 2 and develops["n"] == 2  # spark→develop, critique weak, respark→redevelop
    assert idea == "developed(raw spark 2)"


def test_ideator_develop_stops_early_on_strong_idea(clean_env, monkeypatch) -> None:
    from app.graph import exploration
    from app.services import ideation

    monkeypatch.setattr(
        exploration, "ideate_one", lambda pid, t, *, lens_tweak=None, brief_context="": ("spark", "external_ideator")
    )
    monkeypatch.setattr(exploration, "_develop_seed", lambda pid, t, seed, ctx: "a strong developed idea")
    monkeypatch.setattr(
        ideation, "critique_idea", lambda pid, label, idea, strategy=None: ideation.IdeaCritiqueResult(score=4.8)
    )
    idea, brain = exploration.ideate_iterative("p", Territory(label="T", lens="l"))
    assert idea == "a strong developed idea" and brain == "external_ideator+glm"


def test_ideate_iterative_uses_llm_idea_as_is_when_ideator_absent(clean_env, monkeypatch) -> None:
    # No real external ideator (brain != "external_ideator") -> ideate_one's grounded LLM idea
    # is used directly, no develop step.
    from app.graph import exploration

    monkeypatch.setattr(
        exploration, "ideate_one", lambda pid, t, *, lens_tweak=None, brief_context="": ("glm idea", "glm")
    )
    idea, brain = exploration.ideate_iterative("p", Territory(label="T", lens="l"))
    assert idea == "glm idea" and brain == "glm"


def test_invalid_mode_rejected_at_create(client) -> None:
    r = client.post("/api/projects", json={**BRIEF_BODY, "ideation_mode": "telepathy"})
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# brief grounding: the ideators must see the real brand/brief, not just the    #
# territory label (regression — off-brief drift when only the label was sent). #
# --------------------------------------------------------------------------- #
def test_brief_context_composed_from_state(clean_env) -> None:
    from app.graph.exploration import brief_context
    from app.models.artifacts import Brief, CreativeBrief, Strategy

    state = {
        "brief": Brief(brief="Reposition the premium nutrition brand", brand_name="Example Nutrition Co.", audience="new parents"),
        "strategy": Strategy(positioning="the guided-development brand", key_message="every bite a building block"),
        "creative_brief": CreativeBrief(
            objective="make science feel like care", audience="new parents", key_message="building blocks", tone="warm"
        ),
    }
    ctx = brief_context(state)
    for needle in ("Example Nutrition Co.", "premium nutrition", "new parents", "guided-development", "building block", "care"):
        assert needle in ctx, f"{needle!r} missing from brief context"


def test_ideator_receives_full_brief_not_just_label(clean_env, monkeypatch) -> None:
    from app.graph import exploration
    from app.models.artifacts import Territory

    captured = {}

    def fake_ideator(creative_brief, territory, n_ideas=1):
        captured["cb"] = creative_brief
        return [{"big_idea": "an on-brief idea"}]

    monkeypatch.setattr(exploration, "ideator_generate", fake_ideator)

    class _S:
        ideator_mode = "real"
        IDEATOR_FALLBACK = "glm"

    monkeypatch.setattr(exploration, "get_settings", lambda: _S())
    ctx = "Brand: Example Nutrition Co.\nBrief: nutrition-science led meals"
    idea, brain = exploration.ideate_one(
        "p", Territory(label="The Quiet Expert", lens="calm"), brief_context=ctx
    )
    assert brain == "external_ideator" and idea == "an on-brief idea"
    # the label alone is NOT enough — the brand + brief must be in the prompt
    assert "Example Nutrition Co." in captured["cb"] and "nutrition-science" in captured["cb"]
    assert "The Quiet Expert" in captured["cb"]  # territory still present too
