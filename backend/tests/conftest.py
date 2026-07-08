"""Shared test fixtures/helpers for the backend suite.

Provides a clean-environment fixture so provider resolution is exercised
against a fully empty environment (the keyless-first invariant).
"""

from __future__ import annotations

import os
import tempfile

import pytest
import pytest_asyncio

# CRITICAL — isolate the app's on-disk stores BEFORE any app module is imported.
# app.config computes DATA_DIR at import; app.main's lifespan (run by every
# TestClient(app)) opens the registry + graph checkpointer there and calls
# resume_all(). Without this override a test run RESUMES the operator's real
# in-flight projects under the test env (keyless => mock) and checkpoints mock
# output into their real runs. Set once per test session, honored via
# APP_DATA_DIR in app.config.
os.environ.setdefault("APP_DATA_DIR", tempfile.mkdtemp(prefix="creativeagent-tests-"))

# Every environment variable that drives provider resolution or tuning.
# Cleared so the empty-env contract is exercised deterministically.
_RELEVANT_ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_MODEL",
    "CRITIC_MODEL",
    "MODEL_PROVIDER",
    "MODEL_API_KEY",
    "MODEL_BASE_URL",
    "GENERATOR_MODEL",
    "GENERATOR_CRITIC_MODEL",
    "ZAI_API_KEY",
    "CONCEPTIAL_BASE_URL",
    "CONCEPTIAL_API_KEY",
    "IDEATOR_FALLBACK",
    "TAVILY_API_KEY",
    "EMBEDDINGS_BACKEND",
    "IMAGE_GEN_PROVIDER",
    "IMAGE_GEN_MODEL",
    "FAL_KEY",
    "REPLICATE_API_TOKEN",
    "OPENAI_API_KEY",
    "IMAGE_SOURCE_PROVIDER",
    "PEXELS_API_KEY",
    "UNSPLASH_ACCESS_KEY",
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "ASK_CLARIFYING_QUESTIONS",
    "K",
    "SKETCH_COUNT",
    "MOODBOARD_SIZE",
    "MOODBOARD_GENERATED_RATIO",
    "DIVERGENCE_WARN_MIN",
    "REFINE_ON_FINALIZE",
)


@pytest.fixture(autouse=True)
def _disable_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force settings to ignore any local ``.env`` file during tests.

    The keyless-first contract ("empty env => every provider mock/disabled")
    must hold regardless of an operator's local ``.env`` — which *will* exist
    from Stage 07 onward (real provider keys). ``get_settings()`` honors this
    flag by passing ``_env_file=None``, so only the real process environment
    (which the tests control via monkeypatch) drives resolution.
    """
    monkeypatch.setenv("APP_DISABLE_DOTENV", "1")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove all provider/tuning env vars so resolution starts from empty."""
    for key in _RELEVANT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.fixture
def sneaker_brief():
    """The canonical demo brief used by graph/API tests."""
    from app.models.artifacts import Brief

    return Brief(
        brief="Launch a sustainable sneaker brand for runners sick of greenwashing.",
        brand_name="",
        audience="runners frustrated by greenwashing",
        constraints=[],
    )


@pytest_asyncio.fixture
async def graph_manager(tmp_path, clean_env):
    """A live RunManager over tmp_path storage + an open AsyncSqliteSaver (keyless).

    Yields ``(run_manager, registry)``.
    """
    from app.graph.runner import RunManager
    from app.storage.checkpoint import open_checkpointer
    from app.storage.db import init_db, make_engine, make_sessionmaker
    from app.storage.repo import EventBus, EventRepo, RegistryRepo

    engine = make_engine(f"sqlite:///{tmp_path}/app.sqlite")
    init_db(engine)
    sm = make_sessionmaker(engine)
    bus = EventBus()
    registry = RegistryRepo(sm)
    events = EventRepo(sm, bus)
    async with open_checkpointer(f"{tmp_path}/graph.sqlite") as saver:
        yield RunManager(registry, events, bus, saver), registry
