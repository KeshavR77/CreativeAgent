"""Chat-model resolution + structured-output repair loop (§8.1/§8.4).

`get_chat_model(role)` is model-agnostic: keyless it returns the mock; otherwise
it resolves the provider from config (`model_provider`) — Anthropic, or ANY
OpenAI-compatible endpoint (GLM/z.ai, OpenAI, DeepSeek, …) via base_url + key. The
`critic` role resolves a distinct critic model (real-vs-real independence enforced).

`generate_structured` wraps `with_structured_output(..., include_raw=True)` with
a one-shot repair loop: if the raw output does not parse, strip ``` fences and
retry once; a second failure raises `AgentOutputError` (the node fails, and the
graph's RetryPolicy excludes this error from retries).
"""

from __future__ import annotations

import contextvars
import logging
import os
import re
from typing import Any, Type, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.services.mock_chat import MockChatModel

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger("app.models_svc")

CRITIC_ROLE = "critic"

# Usage from the most recent structured call, scoped per-context (each fan-out
# branch runs in its own thread/context), so a node can build a CostRecord with
# real token counts. Empty for the mock (0 tokens).
_LAST_USAGE: contextvars.ContextVar = contextvars.ContextVar("last_structured_usage", default=None)


def last_usage() -> dict:
    return _LAST_USAGE.get() or {}


def reset_usage() -> None:
    """Clear the per-context usage accumulator. Each graph node/branch runs in its
    own forked context (so it starts clean); this is mainly for direct-call tests."""
    _LAST_USAGE.set({})


def _accumulate_usage(usage: dict) -> None:
    """Add one call's token usage to the per-context running total, so a node (or a
    fan-out branch making several calls) records the sum, not just the last call."""
    current = _LAST_USAGE.get() or {}
    _LAST_USAGE.set(
        {
            "input_tokens": int(current.get("input_tokens", 0)) + int(usage.get("input_tokens", 0) or 0),
            "output_tokens": int(current.get("output_tokens", 0)) + int(usage.get("output_tokens", 0) or 0),
        }
    )


_FENCE_LEAD = re.compile(r"^```[^\n]*\n?")
_FENCE_TRAIL = re.compile(r"\n?```\s*$")


class AgentOutputError(Exception):
    """A model's structured output could not be parsed, even after one repair."""


def strip_code_fences(text: str) -> str:
    """Remove a leading ```/```json fence and a trailing ``` fence."""
    t = text.strip()
    if t.startswith("```"):
        t = _FENCE_LEAD.sub("", t)
        t = _FENCE_TRAIL.sub("", t)
    return t.strip()


def parse_with_repair(raw_content: str, schema: Type[T]) -> T:
    """Parse `raw_content` into `schema`, repairing fenced JSON once."""
    try:
        return schema.model_validate_json(raw_content)
    except (ValidationError, ValueError):
        pass
    try:
        return schema.model_validate_json(strip_code_fences(raw_content))
    except (ValidationError, ValueError) as exc:
        raise AgentOutputError(f"could not parse {schema.__name__} output after repair") from exc


def generate_structured(model: Any, messages: Any, schema: Type[T]) -> T:
    """Invoke `model` for structured `schema` output, applying the repair loop.

    Works with any model whose `with_structured_output(schema, include_raw=True)`
    returns the langchain `{raw, parsed, parsing_error}` shape.
    """
    structured = model.with_structured_output(schema, include_raw=True)
    result = structured.invoke(messages)
    if isinstance(result, dict):
        raw = result.get("raw")
        _accumulate_usage(getattr(raw, "usage_metadata", None) or {})
        parsed = result.get("parsed")
        if parsed is not None:
            return parsed
        content = getattr(raw, "content", "") if raw is not None else ""
        return parse_with_repair(content, schema)
    _accumulate_usage({})
    return result  # model returned the instance directly


def get_chat_model(
    role: str, *, project_id: str = "", temperature: float = 0.7, seed_extra: str = ""
) -> BaseChatModel:
    """Resolve a chat model for `role`, model-agnostically.

    Mock when keyless; otherwise whichever provider ``settings.model_provider``
    resolves to — Anthropic, or ANY OpenAI-compatible endpoint (GLM/z.ai, OpenAI,
    DeepSeek, …). ``seed_extra`` (e.g. a territory label) is folded into the mock
    seed so parallel branches produce distinct, deterministic output (§8.2).
    """
    settings = get_settings()
    provider = settings.model_provider
    if provider == "mock":
        # Loud when a keyed environment unexpectedly degrades to the mock —
        # selection depends only on env/settings, so this firing on a keyed
        # server means the env didn't reach this thread/process as expected.
        logger.warning(
            "get_chat_model resolved MOCK for role=%s (anthropic_key=%s model_key=%s cwd=%s)",
            role,
            bool(settings.ANTHROPIC_API_KEY),
            bool(settings.MODEL_API_KEY),
            os.getcwd(),
        )
        return MockChatModel(seed=f"{project_id}:{role}:{temperature}:{seed_extra}", role=role)
    return _build_real_model(settings, provider, resolve_model_name(role, settings), temperature)


def _build_real_model(settings, provider: str, model_name: str, temperature: float) -> BaseChatModel:
    """Construct a real chat model. Imports are lazy so keyless boot (and an
    Anthropic-only install) never needs another provider's SDK."""
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        # Key + base URL come from Settings (the same source as the provider
        # DECISION), never implicitly from os.environ — otherwise a process
        # where .env loaded but nothing was exported claims "real" and then
        # authenticates with an empty key against the wrong host (§split-brain).
        kwargs: dict = {}
        if settings.ANTHROPIC_API_KEY:
            kwargs["api_key"] = settings.ANTHROPIC_API_KEY
        if settings.ANTHROPIC_BASE_URL:
            kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
        # Explicit timeout: the SDK default (~10 min) lets one stalled stream hang
        # a whole fan-out branch; 120s + retries fails fast and recovers instead.
        return ChatAnthropic(
            model=model_name,
            temperature=temperature,
            max_retries=5,
            timeout=120.0,
            streaming=True,
            **kwargs,
        )
    if provider == "openai_compatible":
        # Any OpenAI-compatible endpoint via base_url + key (needs langchain-openai).
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_retries=5,
            timeout=120.0,
            streaming=True,
            api_key=settings.MODEL_API_KEY,
            base_url=settings.MODEL_BASE_URL,
        )
    raise ValueError(f"unknown model provider: {provider!r}")


def resolve_model_name(role: str, settings) -> str:
    """Generator vs critic model id for the active provider. Enforces critic
    independence (§8.1): a real critic must use a model distinct from the
    generator, or the critique isn't independent."""
    generator = settings.active_generator_model
    critic = settings.active_critic_model
    if role == CRITIC_ROLE:
        if critic == generator:
            raise ValueError(
                "critic model must differ from the generator model "
                "(the critic must be independent of the generator)"
            )
        return critic
    return generator
