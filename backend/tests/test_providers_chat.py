"""Real chat-provider tests (Stage 07, §8.1/§16).

Config/constructor-level only — CI has ZERO keys and makes NO network calls
(ChatAnthropic is monkeypatched). Enforces critic independence and cost tracking;
the keyless path must still resolve to the mock (mock-first regression guard).
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.services.models import get_chat_model, resolve_model_name, reset_usage


def test_keyless_still_resolves_mock(clean_env) -> None:
    assert get_chat_model("critic", project_id="p")._llm_type == "mock-chat"


def test_resolve_model_name_per_role(clean_env) -> None:
    clean_env.setenv("CLAUDE_MODEL", "claude-gen")
    clean_env.setenv("CRITIC_MODEL", "claude-critic")
    s = get_settings()
    assert resolve_model_name("strategist", s) == "claude-gen"
    assert resolve_model_name("critic", s) == "claude-critic"


def test_critic_independence_violation_raises(clean_env) -> None:
    clean_env.setenv("CLAUDE_MODEL", "claude-same")
    clean_env.setenv("CRITIC_MODEL", "claude-same")
    with pytest.raises(ValueError):
        resolve_model_name("critic", get_settings())


def test_real_branch_constructs_with_resolved_model(clean_env, monkeypatch) -> None:
    clean_env.setenv("ANTHROPIC_API_KEY", "unit-test-key")  # non-empty, no real secret
    clean_env.setenv("CLAUDE_MODEL", "claude-gen")
    clean_env.setenv("CRITIC_MODEL", "claude-critic")

    import langchain_anthropic

    captured: dict = {}

    class FakeChatAnthropic:
        def __init__(self, **kw):
            captured.clear()
            captured.update(kw)

    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", FakeChatAnthropic)

    get_chat_model("critic", project_id="p", temperature=0.3)
    assert captured["model"] == "claude-critic"
    assert captured["temperature"] == 0.3

    get_chat_model("strategist")
    assert captured["model"] == "claude-gen"


def test_real_branch_enforces_critic_independence(clean_env, monkeypatch) -> None:
    clean_env.setenv("ANTHROPIC_API_KEY", "unit-test-key")
    clean_env.setenv("CLAUDE_MODEL", "claude-same")
    clean_env.setenv("CRITIC_MODEL", "claude-same")

    import langchain_anthropic

    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", lambda **kw: None)
    with pytest.raises(ValueError):
        get_chat_model("critic")


def test_generate_structured_accumulates_usage_for_cost(clean_env) -> None:
    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableLambda
    from pydantic import BaseModel

    from app.services.models import generate_structured, last_usage

    class Toy(BaseModel):
        a: int

    class StubModel:
        def with_structured_output(self, schema, *, include_raw=False, **kw):
            def _inv(_messages):
                raw = AIMessage(
                    content="{}",
                    usage_metadata={"input_tokens": 130, "output_tokens": 22, "total_tokens": 152},
                )
                return {"raw": raw, "parsed": Toy(a=1), "parsing_error": None}

            return RunnableLambda(_inv)

    reset_usage()
    generate_structured(StubModel(), [], Toy)
    generate_structured(StubModel(), [], Toy)  # a 2nd call in the same context accumulates (fan-out branch)
    usage = last_usage()
    assert usage["input_tokens"] == 260 and usage["output_tokens"] == 44


def test_mock_records_zero_usage(clean_env) -> None:
    from app.models.artifacts import Strategy
    from app.services.models import generate_structured, get_chat_model, last_usage

    reset_usage()
    generate_structured(get_chat_model("strategist", project_id="p"), [], Strategy)
    usage = last_usage()
    assert usage.get("input_tokens", 0) == 0 and usage.get("output_tokens", 0) == 0  # mock -> 0 tokens
