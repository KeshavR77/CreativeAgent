"""Structured-output repair-loop tests (Stage 03, §8.4/§16).

Contract: parse the model's raw output; on failure make ONE repair attempt that
strips ``` fences and re-parses; a second failure raises `AgentOutputError`
(the node then fails, and RetryPolicy excludes that error from retries).
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel

from app.services.models import (
    AgentOutputError,
    generate_structured,
    parse_with_repair,
    strip_code_fences,
)


class Toy(BaseModel):
    a: int
    b: str


def test_parse_valid_json_no_repair() -> None:
    obj = parse_with_repair('{"a": 1, "b": "x"}', Toy)
    assert (obj.a, obj.b) == (1, "x")


def test_parse_fenced_json_one_repair() -> None:
    obj = parse_with_repair('```json\n{"a": 2, "b": "y"}\n```', Toy)
    assert obj.a == 2


def test_parse_plain_fence_one_repair() -> None:
    obj = parse_with_repair('```\n{"a": 3, "b": "z"}\n```', Toy)
    assert obj.a == 3


def test_parse_double_failure_raises_agent_output_error() -> None:
    with pytest.raises(AgentOutputError):
        parse_with_repair("not json at all {{{", Toy)


def test_parse_fenced_but_still_garbage_raises() -> None:
    with pytest.raises(AgentOutputError):
        parse_with_repair("```json\nstill not json\n```", Toy)


def test_strip_code_fences() -> None:
    assert strip_code_fences('```json\n{"a":1}\n```') == '{"a":1}'
    assert strip_code_fences('```\n{"a":1}\n```') == '{"a":1}'
    assert strip_code_fences('{"a":1}') == '{"a":1}'


# --- generate_structured: repair branch exercised via a stub model -------- #
class _StubModel:
    """Minimal model whose structured runnable returns unparsed raw content."""

    def __init__(self, raw_content: str, parsed=None) -> None:
        self._raw = raw_content
        self._parsed = parsed

    def with_structured_output(self, schema, *, include_raw: bool = False, **kw):
        def _invoke(_messages):
            return {
                "raw": AIMessage(content=self._raw),
                "parsed": self._parsed,
                "parsing_error": None,
            }

        return RunnableLambda(_invoke)


def test_generate_structured_repairs_when_parsed_is_none() -> None:
    stub = _StubModel('```json\n{"a": 9, "b": "q"}\n```', parsed=None)
    obj = generate_structured(stub, [], Toy)
    assert obj.a == 9


def test_generate_structured_returns_parsed_when_present() -> None:
    stub = _StubModel("irrelevant", parsed=Toy(a=5, b="ok"))
    assert generate_structured(stub, [], Toy).a == 5


def test_generate_structured_raises_on_unrepairable() -> None:
    stub = _StubModel("hopeless garbage", parsed=None)
    with pytest.raises(AgentOutputError):
        generate_structured(stub, [], Toy)
