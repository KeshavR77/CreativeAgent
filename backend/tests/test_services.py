"""Mock model + search service tests (Stage 03, §8.1/§8.2/§8.5/§16).

Keyless: `get_chat_model` returns a deterministic `MockChatModel`; structured
output yields valid, seed-deterministic artifacts; search is backed by the
bundled corpus. All assertions run under an empty environment.
"""

from __future__ import annotations

from app.models.artifacts import (
    CreativeBrief,
    ResearchDossier,
    SourceRef,
    Strategy,
    VerbalIdentity,
)
from app.services.models import generate_structured, get_chat_model
from app.services.search import search


def test_get_chat_model_is_mock_when_keyless(clean_env) -> None:
    m = get_chat_model("strategist", project_id="p1")
    assert m._llm_type == "mock-chat"


def test_mock_structured_output_valid(clean_env) -> None:
    m = get_chat_model("strategist", project_id="p1")
    result = m.with_structured_output(Strategy, include_raw=True).invoke([])
    assert result["parsed"] is not None
    assert isinstance(result["parsed"], Strategy)
    # raw content is valid JSON of the same instance (so the repair path also works)
    assert result["raw"].content


def test_mock_structured_output_deterministic(clean_env) -> None:
    a = get_chat_model("strategist", project_id="p1")
    b = get_chat_model("strategist", project_id="p1")
    sa = a.with_structured_output(Strategy, include_raw=True).invoke([])["parsed"]
    sb = b.with_structured_output(Strategy, include_raw=True).invoke([])["parsed"]
    assert sa == sb  # same seed -> identical output


def test_mock_structured_output_varies_by_project(clean_env) -> None:
    a = get_chat_model("strategist", project_id="p1")
    b = get_chat_model("strategist", project_id="p2")
    sa = a.with_structured_output(Strategy, include_raw=True).invoke([])["parsed"]
    sb = b.with_structured_output(Strategy, include_raw=True).invoke([])["parsed"]
    assert sa != sb  # different project_id -> different output (divergence-ready)


def test_generate_structured_builds_spine_artifacts(clean_env) -> None:
    dossier = generate_structured(get_chat_model("researcher", project_id="p1"), [], ResearchDossier)
    assert isinstance(dossier, ResearchDossier)

    vi = generate_structured(get_chat_model("namer", project_id="p1"), [], VerbalIdentity)
    assert isinstance(vi, VerbalIdentity)
    assert vi.screened is False  # honesty marker survives generation

    cb = generate_structured(get_chat_model("writer", project_id="p1"), [], CreativeBrief)
    assert isinstance(cb, CreativeBrief)


def test_search_keyless_returns_sources(clean_env) -> None:
    results = search("sustainable sneaker greenwashing", k=4)
    assert 1 <= len(results) <= 4
    assert all(isinstance(r, SourceRef) for r in results)


def test_search_is_deterministic(clean_env) -> None:
    q = "sustainable sneaker greenwashing"
    assert search(q, k=4) == search(q, k=4)
