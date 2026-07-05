"""Typed settings + provider resolution for the AI Creative Agency backend.

Design invariants (Stage 01 contract §3):
- Tolerates a fully empty environment; NEVER raises on a missing key.
- No field is required-without-default.
- Boolean env parsing: {"1","true","yes","on"} (case-insensitive) => True.
- Provider resolution lives here (not in the route). ``health_snapshot()``
  returns the exact ``/api/health`` payload.
- NO heavy ML imports (torch / sentence_transformers) at module load;
  ``EMBEDDINGS_BACKEND`` resolution is pure string logic. Model loading is
  deferred to later sub-plans.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("app.config")

# Directory layout: data/ and data/generated/ must exist at import/startup.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _BACKEND_ROOT / "data"
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

    # --- Claude ---
    ANTHROPIC_API_KEY: str | None = None
    CLAUDE_MODEL: str = "claude-sonnet-4-5"
    CRITIC_MODEL: str = "claude-opus-4-1"

    # --- Conceptial ---
    CONCEPTIAL_BASE_URL: str | None = None
    CONCEPTIAL_API_KEY: str | None = None
    IDEATOR_FALLBACK: str = "claude_high_temp"

    # --- Search + embeddings ---
    TAVILY_API_KEY: str | None = None
    EMBEDDINGS_BACKEND: str | None = None

    # --- Image generation ---
    IMAGE_GEN_PROVIDER: str | None = None
    IMAGE_GEN_MODEL: str = "flux/schnell"
    FAL_KEY: str | None = None
    REPLICATE_API_TOKEN: str | None = None
    OPENAI_API_KEY: str | None = None

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
    def conceptial_mode(self) -> str:
        return "real" if _non_empty(self.CONCEPTIAL_BASE_URL) else "mock"

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
        """Exact /api/health payload (contract §4)."""
        return {
            "status": "ok",
            "providers": {
                "claude": self.claude_mode,
                "conceptial": self.conceptial_mode,
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
        logger.info("provider claude=%s", self.claude_mode)
        logger.info("provider conceptial=%s", self.conceptial_mode)
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
