"""Deterministic mock chat model.

`MockChatModel` stands in for a real Claude model when `ANTHROPIC_API_KEY` is
empty (the keyless-first default). Output is deterministic — seeded by the
model's `seed` (project_id + role + temperature) plus the requested schema — so
mock runs are reproducible and later develop measurable divergence once a
territory label enters the seed.

Structured output is produced by `build_fixture`, a generic, validator-respecting
fixture generator over any Pydantic model. This keeps the mock schema-aware
without hand-writing output per node; format-constrained schemas introduced in
later stages (e.g. hex palettes, >=50-word critiques) can register bespoke
builders if the generic one is insufficient.
"""

from __future__ import annotations

import hashlib
import types
from typing import Any, Callable, Literal, Union, get_args, get_origin

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

_WORDS = (
    "signal", "proof", "honest", "trail", "dawn", "grounded", "raw", "seam",
    "earth", "stride", "candid", "tread", "roots", "current", "plainspoken",
)

_UNION_ORIGINS: set = {Union}
if hasattr(types, "UnionType"):  # PEP 604  `X | Y`
    _UNION_ORIGINS.add(types.UnionType)


def _h(s: str) -> int:
    """Stable (cross-process) hash — `hash()` is salted, so use md5."""
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16)


def _phrase(seed: str, n: int = 6) -> str:
    base = _h(seed)
    return " ".join(_WORDS[(base >> (i * 3)) % len(_WORDS)] for i in range(max(1, n)))


def _is_model(t: Any) -> bool:
    return isinstance(t, type) and issubclass(t, BaseModel)


def _gen(ann: Any, seed: str, name: str) -> Any:
    origin = get_origin(ann)
    if origin in _UNION_ORIGINS:  # Optional[X] / X | None -> generate the concrete arm
        args = [a for a in get_args(ann) if a is not type(None)]
        return _gen(args[0], seed, name) if args else None
    if origin is Literal:
        opts = get_args(ann)
        return opts[_h(seed) % len(opts)]
    if origin in (list, tuple, set, frozenset):
        args = get_args(ann)
        inner = args[0] if args else str
        return [_gen(inner, f"{seed}:{i}", name) for i in range(2)]
    if origin is dict:
        return {}
    if ann is str:
        return _phrase(seed, 4)
    if ann is bool:
        return bool(_h(seed) % 2)
    if ann is int:
        return _h(seed) % 5 + 1  # 1..5 (safe for rubric-style ranges)
    if ann is float:
        return round((_h(seed) % 1000) / 1000.0, 3)
    if _is_model(ann):
        return build_fixture(ann, seed)
    return None


# Bespoke builders for schemas the generic generator can't satisfy (e.g. a
# >=50-word case_against, hex-constrained colours). Registered at import time by
# whichever module owns the schema.
_BUILDERS: dict[type, Callable[[str], BaseModel]] = {}


def register_builder(schema: type, fn: Callable[[str], BaseModel]) -> None:
    _BUILDERS[schema] = fn


def build_fixture(model: type[BaseModel], seed: str) -> BaseModel:
    """Build a deterministic, valid instance of `model` seeded by `seed`.

    A registered bespoke builder wins; otherwise each field is generated
    generically from its annotation.
    """
    bespoke = _BUILDERS.get(model)
    if bespoke is not None:
        return bespoke(seed)
    data = {
        name: _gen(field.annotation, f"{seed}:{name}", name)
        for name, field in model.model_fields.items()
    }
    return model(**data)


class MockChatModel(BaseChatModel):
    """A deterministic, keyless stand-in for a Claude chat model."""

    seed: str = "seed"
    role: str = "assistant"

    @property
    def _llm_type(self) -> str:
        return "mock-chat"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        text = f"[mock:{self.role}] {_phrase(self.seed + ':gen', 10)}"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    def with_structured_output(  # type: ignore[override]
        self, schema, *, include_raw: bool = False, **kwargs
    ) -> Runnable:
        seed = f"{self.seed}:{getattr(schema, '__name__', str(schema))}"

        def _invoke(_messages: Any) -> Any:
            instance = build_fixture(schema, seed)
            if include_raw:
                return {
                    "raw": AIMessage(content=instance.model_dump_json()),
                    "parsed": instance,
                    "parsing_error": None,
                }
            return instance

        return RunnableLambda(_invoke)


# --------------------------------------------------------------------------- #
# bespoke builders (registered at import) for validator-constrained schemas    #
# --------------------------------------------------------------------------- #
def _build_critique_score(seed: str) -> BaseModel:
    """A valid CritiqueScore: 1-5 rubric scores + a >=50-word case_against.

    ``verdict`` and ``critic_model`` are placeholders — the critic node
    recomputes the verdict in code and records the real critic model.
    """
    from app.models.artifacts import CritiqueScore

    return CritiqueScore(
        distinctiveness=_h(seed + ":distinct") % 5 + 1,
        strategic_fit=_h(seed + ":fit") % 5 + 1,
        memorability=_h(seed + ":mem") % 5 + 1,
        audience_resonance=_h(seed + ":aud") % 5 + 1,
        feasibility=_h(seed + ":feas") % 5 + 1,
        case_against=_phrase(seed + ":case", 55),
        verdict="revise",
        critic_model="mock-chat",
    )


def _build_palette_color(seed: str) -> BaseModel:
    """A PaletteColor with a valid #RRGGBB hex (the generic builder can't)."""
    from app.models.artifacts import PaletteColor

    return PaletteColor(
        name=_phrase(seed + ":name", 2),
        hex=f"#{_h(seed + ':hex') % 0x1000000:06X}",
        role=_phrase(seed + ":role", 1),
    )


def _register_default_builders() -> None:
    from app.models.artifacts import CritiqueScore, PaletteColor

    register_builder(CritiqueScore, _build_critique_score)
    register_builder(PaletteColor, _build_palette_color)


_register_default_builders()
