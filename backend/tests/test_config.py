"""Provider-resolution unit tests.

Each real-flip is asserted independently via monkeypatched env vars. Config
must tolerate a fully empty environment and never raise on missing keys.
"""

from __future__ import annotations

import importlib

import pytest


def _snapshot() -> dict:
    """Reimport config fresh and return the health snapshot for current env."""
    import app.config as config

    importlib.reload(config)
    # Route through get_settings() so the APP_DISABLE_DOTENV guard applies —
    # direct Settings() construction would still read a local .env file.
    return config.get_settings().health_snapshot()


def test_empty_env_imports_without_raising(clean_env) -> None:
    # Importing config and main under an empty env must not raise.
    import app.config as config
    import app.main as main

    importlib.reload(config)
    importlib.reload(main)

    snap = config.get_settings().health_snapshot()
    assert snap["status"] == "ok"
    assert snap["providers"]["claude"] == "mock"
    assert snap["providers"]["ideator"] == "mock"
    assert snap["providers"]["search"] == "mock"
    assert snap["providers"]["embeddings"] == "mock"
    assert snap["image_gen"] == {"enabled": False, "provider": None}
    assert snap["image_source"] == {"enabled": False, "provider": None}
    assert snap["tracing"] is False


def test_claude_flips_real(clean_env) -> None:
    clean_env.setenv("ANTHROPIC_API_KEY", "x")
    assert _snapshot()["providers"]["claude"] == "real"


def test_ideator_flips_real(clean_env) -> None:
    clean_env.setenv("IDEATOR_BASE_URL", "http://localhost:9999")
    assert _snapshot()["providers"]["ideator"] == "real"


def test_search_flips_real(clean_env) -> None:
    clean_env.setenv("TAVILY_API_KEY", "x")
    assert _snapshot()["providers"]["search"] == "real"


@pytest.mark.parametrize("backend", ["auto", "minilm", "tfidf", "AUTO", "MiniLM"])
def test_embeddings_real_backends(clean_env, backend: str) -> None:
    clean_env.setenv("EMBEDDINGS_BACKEND", backend)
    assert _snapshot()["providers"]["embeddings"] == "real"


@pytest.mark.parametrize("backend", ["mock", "", "something-else"])
def test_embeddings_mock_backends(clean_env, backend: str) -> None:
    clean_env.setenv("EMBEDDINGS_BACKEND", backend)
    assert _snapshot()["providers"]["embeddings"] == "mock"


def test_embeddings_unset_is_mock(clean_env) -> None:
    assert _snapshot()["providers"]["embeddings"] == "mock"


def test_image_gen_enabled_echoes_provider(clean_env) -> None:
    clean_env.setenv("IMAGE_GEN_PROVIDER", "fal")
    assert _snapshot()["image_gen"] == {"enabled": True, "provider": "fal"}


def test_image_source_enabled_echoes_provider(clean_env) -> None:
    clean_env.setenv("IMAGE_SOURCE_PROVIDER", "pexels")
    assert _snapshot()["image_source"] == {"enabled": True, "provider": "pexels"}


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "On"])
def test_tracing_truthy(clean_env, value: str) -> None:
    clean_env.setenv("LANGSMITH_TRACING", value)
    assert _snapshot()["tracing"] is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "nope"])
def test_tracing_falsy(clean_env, value: str) -> None:
    clean_env.setenv("LANGSMITH_TRACING", value)
    assert _snapshot()["tracing"] is False


def test_tracing_unset_is_false(clean_env) -> None:
    assert _snapshot()["tracing"] is False


def test_whitespace_only_key_is_mock(clean_env) -> None:
    # A whitespace-only value must NOT count as "non-empty".
    clean_env.setenv("ANTHROPIC_API_KEY", "   ")
    assert _snapshot()["providers"]["claude"] == "mock"
