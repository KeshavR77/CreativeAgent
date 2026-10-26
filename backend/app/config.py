"""Typed settings + provider resolution for the AI Creative Agency backend.

Design invariants:
- Tolerates a fully empty environment; NEVER raises on a missing key.
- No field is required-without-default.
- Boolean env parsing: {"1","true","yes","on"} (case-insensitive) => True.
- Provider resolution lives here (not in the route). ``health_snapshot()``
  returns the exact ``/api/health`` payload.
- NO heavy ML imports (torch / sentence_transformers) at module load;
  ``EMBEDDINGS_BACKEND`` resolution is pure string logic. Model loading is
  deferred until first use.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("app.config")

# Directory layout: data/ and data/generated/ must exist at import/startup.
# APP_DATA_DIR overrides the location — REQUIRED for tests: TestClient(app) runs
# the real lifespan (registry + checkpointer + resume_all), and pointing that at
# the live data/ lets a test run RESUME real in-flight projects under the test
# env (mock, keyless) and checkpoint mock output into real runs.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("APP_DATA_DIR") or (_BACKEND_ROOT / "data"))
GENERATED_DIR = DATA_DIR / "generated"

# Embeddings backends that resolve to "real" (case-insensitive).
_REAL_EMBEDDINGS_BACKENDS = frozenset({"auto", "minilm", "tfidf"})
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _truthy(value: str | None) -> bool:
    """Parse a boolean env value. Empty/None/unknown => False."""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY


def _non_empty(value: str | None) -> bool:
    """True iff value is present and not empty/whitespace-only."""
    return bool(value is not None and value.strip())


def _ensure_data_dirs() -> None:
    """Create data/ and data/generated/ without failing the import."""
    try:
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - defensive; never block boot
        logger.warning("could not create data directories: %s", exc)


class Settings(BaseSettings):
    """All provider/tuning keys. Every field optional; empty env is valid."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- Claude / Anthropic-compatible endpoint (e.g. z.ai GLM) ---
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_BASE_URL: str | None = None  # unset => api.anthropic.com
    CLAUDE_MODEL: str = "claude-sonnet-4-5"
    CRITIC_MODEL: str = "claude-opus-4-1"

    # --- Model provider (model-agnostic generation) ---
    # Auto-detected from keys unless MODEL_PROVIDER is set: ANTHROPIC_API_KEY ->
    # "anthropic"; MODEL_API_KEY -> "openai_compatible"; else "mock". The
    # "openai_compatible" provider covers ANY OpenAI-compatible endpoint — GLM/z.ai,
    # OpenAI, DeepSeek, Together, Groq, Ollama — via MODEL_BASE_URL + MODEL_API_KEY.
    MODEL_PROVIDER: str | None = None
    MODEL_API_KEY: str | None = None
    MODEL_BASE_URL: str = "https://api.z.ai/api/paas/v4/"  # default endpoint: GLM (z.ai)
    GENERATOR_MODEL: str = "glm-4.6"             # generator model id (override per provider)
    GENERATOR_CRITIC_MODEL: str = "glm-4.5-air"  # critic model id (MUST differ from the generator)

    # --- External ideator ---
    IDEATOR_BASE_URL: str | None = None
    IDEATOR_API_KEY: str | None = None
    IDEATOR_FALLBACK: str = "claude_high_temp"

    # --- Search + embeddings ---
    TAVILY_API_KEY: str | None = None
    EMBEDDINGS_BACKEND: str | None = None

    # --- Image generation ---
    # IMAGE_GEN_PROVIDER: fal | replicate | openai | zai | mock. "zai" reuses
    # MODEL_API_KEY (or ZAI_API_KEY) — GLM chat + glm-image on one key.
    IMAGE_GEN_PROVIDER: str | None = None
    IMAGE_GEN_MODEL: str = "flux/schnell"
    FAL_KEY: str | None = None
    REPLICATE_API_TOKEN: str | None = None
    OPENAI_API_KEY: str | None = None
    ZAI_API_KEY: str | None = None

    @property
    def zai_image_key(self) -> str | None:
        """Key for the z.ai image lane: ZAI_API_KEY, else MODEL_API_KEY (one-key setups)."""
        return self.ZAI_API_KEY if _non_empty(self.ZAI_API_KEY) else self.MODEL_API_KEY

    # --- Image sourcing ---
    IMAGE_SOURCE_PROVIDER: str | None = None
    PEXELS_API_KEY: str | None = None
    UNSPLASH_ACCESS_KEY: str | None = None

    # --- Tracing ---
    LANGSMITH_TRACING: str | None = None
    LANGSMITH_API_KEY: str | None = None

    # --- Behavior / tuning knobs ---
    ASK_CLARIFYING_QUESTIONS: str | None = "false"
    K: int = 4
    SKETCH_COUNT: int = 3
    MOODBOARD_SIZE: int = 9
    MOODBOARD_GENERATED_RATIO: float = 0.34
    DIVERGENCE_WARN_MIN: float = 0.15
    REFINE_ON_FINALIZE: str | None = "true"

    # ------------------------------------------------------------------
    # Derived provider resolution
    # ------------------------------------------------------------------
    @property
    def claude_mode(self) -> str:
        return "real" if _non_empty(self.ANTHROPIC_API_KEY) else "mock"

    @property
    def model_provider(self) -> str:
        """Active chat provider: 'anthropic' | 'openai_compatible' | 'mock'.

        Explicit ``MODEL_PROVIDER`` wins; otherwise auto-detect from keys (Anthropic
        first, then any OpenAI-compatible ``MODEL_API_KEY``, else the mock)."""
        explicit = (self.MODEL_PROVIDER or "").strip().lower()
        if explicit in ("anthropic", "claude"):
            return "anthropic"
        if explicit in ("openai_compatible", "openai-compatible", "openai", "glm", "zhipu", "zai"):
            return "openai_compatible"
        if explicit == "mock":
            return "mock"
        if _non_empty(self.ANTHROPIC_API_KEY):
            return "anthropic"
        if _non_empty(self.MODEL_API_KEY):
            return "openai_compatible"
        return "mock"

    @property
    def active_generator_model(self) -> str:
        return self.CLAUDE_MODEL if self.model_provider == "anthropic" else self.GENERATOR_MODEL

    @property
    def active_critic_model(self) -> str:
        return self.CRITIC_MODEL if self.model_provider == "anthropic" else self.GENERATOR_CRITIC_MODEL

    @property
    def ideator_mode(self) -> str:
        return "real" if _non_empty(self.IDEATOR_BASE_URL) else "mock"

    @property
    def search_mode(self) -> str:
        return "real" if _non_empty(self.TAVILY_API_KEY) else "mock"

    @property
    def embeddings_mode(self) -> str:
        value = (self.EMBEDDINGS_BACKEND or "").strip().lower()
        return "real" if value in _REAL_EMBEDDINGS_BACKENDS else "mock"

    @property
    def image_gen_enabled(self) -> bool:
        return _non_empty(self.IMAGE_GEN_PROVIDER)

    @property
    def image_gen_provider(self) -> str | None:
        return self.IMAGE_GEN_PROVIDER if self.image_gen_enabled else None

    @property
    def image_source_enabled(self) -> bool:
        return _non_empty(self.IMAGE_SOURCE_PROVIDER)

    @property
    def image_source_provider(self) -> str | None:
        return self.IMAGE_SOURCE_PROVIDER if self.image_source_enabled else None

    @property
    def tracing_enabled(self) -> bool:
        return _truthy(self.LANGSMITH_TRACING)

    @property
    def ask_clarifying_questions(self) -> bool:
        return _truthy(self.ASK_CLARIFYING_QUESTIONS)

    @property
    def refine_on_finalize(self) -> bool:
        return _truthy(self.REFINE_ON_FINALIZE)

    def health_snapshot(self) -> dict:
        """Exact /api/health payload."""
        return {
            "status": "ok",
            "providers": {
                # "claude" is the historical key for the CHAT lane: real whenever
                # ANY chat provider (anthropic-compat or openai-compat) is keyed.
                "claude": "real" if self.model_provider != "mock" else "mock",
                "ideator": self.ideator_mode,
                "search": self.search_mode,
                "embeddings": self.embeddings_mode,
            },
            "image_gen": {
                "enabled": self.image_gen_enabled,
                "provider": self.image_gen_provider,
            },
            "image_source": {
                "enabled": self.image_source_enabled,
                "provider": self.image_source_provider,
            },
            "tracing": self.tracing_enabled,
        }

    def log_providers(self) -> None:
        """Emit exactly one INFO line per provider row (startup logs)."""
        logger.info(
            "model_provider=%s generator=%s critic=%s",
            self.model_provider,
            self.active_generator_model if self.model_provider != "mock" else "mock",
            self.active_critic_model if self.model_provider != "mock" else "mock",
        )
        logger.info("provider claude=%s", self.claude_mode)
        logger.info("provider ideator=%s", self.ideator_mode)
        logger.info("provider search=%s", self.search_mode)
        logger.info("provider embeddings=%s", self.embeddings_mode)
        logger.info(
            "image_gen=%s",
            self.image_gen_provider if self.image_gen_enabled else "disabled",
        )
        logger.info(
            "image_source=%s",
            self.image_source_provider if self.image_source_enabled else "disabled",
        )
        logger.info("tracing=%s", "on" if self.tracing_enabled else "off")


def get_settings() -> Settings:
    """Build a Settings instance from the current environment.

    Never raises on missing keys. Reads live ``os.environ`` each call so tests
    that monkeypatch env vars see fresh resolution.
    """
    return Settings(_env_file=None if os.environ.get("APP_DISABLE_DOTENV") else ".env")


# Ensure the data directory tree exists at import time (never fails the import).
_ensure_data_dirs()
