"""Real chat-provider tests.

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
    clean_env.setenv("ANTHROPIC_API_KEY", "unit-test-key")  # anthropic provider
    clean_env.setenv("CLAUDE_MODEL", "claude-gen")
    clean_env.setenv("CRITIC_MODEL", "claude-critic")
    s = get_settings()
    assert resolve_model_name("strategist", s) == "claude-gen"
    assert resolve_model_name("critic", s) == "claude-critic"


def test_critic_independence_violation_raises(clean_env) -> None:
    clean_env.setenv("ANTHROPIC_API_KEY", "unit-test-key")  # anthropic provider
    clean_env.setenv("CLAUDE_MODEL", "claude-same")
    clean_env.setenv("CRITIC_MODEL", "claude-same")
    with pytest.raises(ValueError):
        resolve_model_name("critic", get_settings())


def test_model_provider_autodetects_from_keys(clean_env) -> None:
    assert get_settings().model_provider == "mock"  # keyless
    clean_env.setenv("MODEL_API_KEY", "glm-key")
    assert get_settings().model_provider == "openai_compatible"  # any OpenAI-compatible endpoint
    clean_env.setenv("ANTHROPIC_API_KEY", "k")
    assert get_settings().model_provider == "anthropic"  # anthropic wins the auto-detect
    clean_env.setenv("MODEL_PROVIDER", "glm")
    assert get_settings().model_provider == "openai_compatible"  # explicit override


def test_openai_compatible_branch_constructs_with_base_url_and_key(clean_env, monkeypatch) -> None:
    import sys
    import types

    clean_env.setenv("MODEL_API_KEY", "glm-key")  # -> openai_compatible provider
    clean_env.setenv("MODEL_BASE_URL", "https://api.z.ai/api/paas/v4/")
    clean_env.setenv("GENERATOR_MODEL", "glm-4.6")
    clean_env.setenv("GENERATOR_CRITIC_MODEL", "glm-4.5-air")

    captured: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kw):
            captured.clear()
            captured.update(kw)

    fake_mod = types.ModuleType("langchain_openai")
    fake_mod.ChatOpenAI = FakeChatOpenAI
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_mod)

    get_chat_model("ideator", temperature=1.0)
    assert captured["model"] == "glm-4.6"
    assert captured["base_url"] == "https://api.z.ai/api/paas/v4/"
    assert captured["temperature"] == 1.0
    assert "api_key" in captured  # key wired through

    get_chat_model("critic")
    assert captured["model"] == "glm-4.5-air"  # distinct critic model


def test_openai_compatible_enforces_critic_independence(clean_env) -> None:
    clean_env.setenv("MODEL_API_KEY", "glm-key")
    clean_env.setenv("GENERATOR_MODEL", "glm-4.6")
    clean_env.setenv("GENERATOR_CRITIC_MODEL", "glm-4.6")  # same as generator -> violation
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


# --------------------------------------------------------------------------- #
# Anthropic content-block normalization (GLM/z.ai over the Anthropic endpoint  #
# may return `content` as a LIST of blocks; the repair path must not crash).   #
# --------------------------------------------------------------------------- #
def test_content_to_text_handles_blocks_and_strings() -> None:
    from app.services.models import content_to_text

    assert content_to_text("plain") == "plain"
    assert content_to_text(None) == ""
    assert content_to_text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "ab"
    assert content_to_text(["x", {"text": "y"}]) == "xy"


def test_parse_with_repair_accepts_list_content() -> None:
    from pydantic import BaseModel

    from app.services.models import parse_with_repair

    class Tiny(BaseModel):
        brief: str

    # A fenced JSON payload delivered as Anthropic content blocks (a list).
    blocks = [{"type": "text", "text": '```json\n{"brief": "hello"}\n```'}]
    out = parse_with_repair(blocks, Tiny)
    assert out.brief == "hello"


def test_generate_structured_normalizes_list_content_on_repair() -> None:
    from pydantic import BaseModel

    from langchain_core.messages import AIMessage

    from app.services.models import generate_structured

    class Tiny(BaseModel):
        brief: str

    class FakeStructured:
        def invoke(self, _messages):
            # parsed=None forces the repair path; raw.content is a block LIST.
            raw = AIMessage(content=[{"type": "text", "text": '{"brief": "ok"}'}])
            return {"raw": raw, "parsed": None, "parsing_error": "x"}

    class FakeModel:
        def with_structured_output(self, _schema, *, include_raw=False, **_kw):
            return FakeStructured()

    out = generate_structured(FakeModel(), "msgs", Tiny)
    assert out.brief == "ok"


def test_parse_with_repair_extracts_json_from_prose() -> None:
    # GLM-style: JSON wrapped in explanation, no code fences. Must still parse.
    from pydantic import BaseModel

    from app.services.models import parse_with_repair

    class Copy(BaseModel):
        headline: str
        cta: str

    prose = (
        'Here is the copy deck for this concept:\n'
        '{"headline": "Never Feed Alone", "cta": "Start the journey"}\n'
        'This works because it centers the parent, not the product.'
    )
    out = parse_with_repair(prose, Copy)
    assert out.headline == "Never Feed Alone" and out.cta == "Start the journey"


def test_extract_json_block_respects_strings_and_nesting() -> None:
    from app.services.models import _extract_json_block

    # braces inside a string value must not end the block early
    text = 'blah {"a": {"b": "has } brace"}, "c": 1} trailing'
    assert _extract_json_block(text) == '{"a": {"b": "has } brace"}, "c": 1}'
    assert _extract_json_block("no json here") is None
