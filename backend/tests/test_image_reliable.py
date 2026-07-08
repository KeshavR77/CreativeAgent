"""The zero-placeholder guarantee: generate_reliable tops up shortfalls with real
images (never placeholders) when the lane is enabled, and the z.ai adapter retries
a flaky image before giving up on the slot."""

from __future__ import annotations

import httpx
import pytest

from app.models.artifacts import ImageRef
from app.services import imagegen


def _ref(i: int) -> ImageRef:
    return ImageRef(
        kind="generated",
        url=f"/generated/p/d/{i}.png",
        provider="zai",
        license="AI-generated",
        gen_model="glm-image",
        gen_prompt=f"prompt {i}",
    )


def test_generate_reliable_returns_exact_count_when_lane_healthy(clean_env, monkeypatch):
    calls = {"n": 0}

    def fake_generate(prompts, *, project_id, direction_id, model=None):
        calls["n"] += 1
        return [_ref(i) for i, _ in enumerate(prompts)]

    monkeypatch.setattr(imagegen, "generate", fake_generate)
    out = imagegen.generate_reliable(["a", "b", "c"], project_id="p", direction_id="d")
    assert len(out) == 3
    assert all(r.kind == "generated" for r in out)
    assert calls["n"] == 1  # no top-up needed


def test_generate_reliable_tops_up_shortfall_with_real_images(clean_env, monkeypatch):
    # First call under-delivers (2 of 3); the top-up round fills the rest.
    seq = [[_ref(0), _ref(1)], [_ref(2)]]

    def fake_generate(prompts, *, project_id, direction_id, model=None):
        return seq.pop(0) if seq else []

    monkeypatch.setattr(imagegen, "generate", fake_generate)
    out = imagegen.generate_reliable(["a", "b", "c"], project_id="p", direction_id="d")
    assert len(out) == 3
    assert all(r.kind == "generated" for r in out)  # NEVER a placeholder


def test_generate_reliable_repeats_real_rather_than_placeholder(clean_env, monkeypatch):
    # Partial outage: only ever one image comes back. The guarantee repeats a real
    # image to fill the board rather than emitting a placeholder.
    def fake_generate(prompts, *, project_id, direction_id, model=None):
        return [_ref(0)]

    monkeypatch.setattr(imagegen, "generate", fake_generate)
    out = imagegen.generate_reliable(["a", "b", "c", "d"], project_id="p", direction_id="d")
    assert len(out) == 4
    assert all(r.kind == "generated" for r in out)
    assert not any(r.kind == "placeholder" for r in out)


def test_generate_reliable_propagates_disabled_lane(clean_env, monkeypatch):
    def fake_generate(prompts, *, project_id, direction_id, model=None):
        raise imagegen.ImageGenUnavailable("disabled")

    monkeypatch.setattr(imagegen, "generate", fake_generate)
    with pytest.raises(imagegen.ImageGenUnavailable):
        imagegen.generate_reliable(["a"], project_id="p", direction_id="d")


def test_zai_one_retries_a_flaky_image(clean_env, monkeypatch, tmp_path):
    # The generation POST 404s once, then succeeds; the CDN then serves bytes.
    from app.config import GENERATED_DIR  # noqa: F401 - ensures data dir import side effects

    state = {"gen_calls": 0}
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            state["gen_calls"] += 1
            if state["gen_calls"] == 1:
                return httpx.Response(500, json={"error": "transient"})
            return httpx.Response(200, json={"data": [{"url": "https://mfile.z.ai/x.png"}]})
        return httpx.Response(200, content=png)  # CDN download

    transport = httpx.MockTransport(handler)
    # monkeypatch time.sleep so the retry backoff doesn't slow the test
    monkeypatch.setattr(imagegen.time, "sleep", lambda *_a, **_k: None)
    api = httpx.Client(base_url="https://api.z.ai", transport=transport)
    cdn = httpx.Client(transport=transport)
    try:
        ref = imagegen._zai_one(api, cdn, "a prompt", "proj", "dir", "glm-image")
    finally:
        api.close()
        cdn.close()
    assert ref is not None
    assert ref.kind == "generated"
    assert ref.provider == "zai"
    assert state["gen_calls"] == 2  # retried once, then succeeded


def test_zai_one_backs_off_on_429_then_succeeds(clean_env, monkeypatch):
    # z.ai rate-limits (429) twice, then serves the image. The adapter must back
    # off and retry rather than give up — and must not sleep for real in tests.
    calls = {"n": 0}
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            calls["n"] += 1
            if calls["n"] <= 2:
                return httpx.Response(429, json={"error": {"code": "1302", "message": "Rate limit reached"}})
            return httpx.Response(200, json={"data": [{"url": "https://mfile.z.ai/x.png"}]})
        return httpx.Response(200, content=png)

    monkeypatch.setattr(imagegen.time, "sleep", lambda *_a, **_k: None)
    api = httpx.Client(base_url="https://api.z.ai", transport=httpx.MockTransport(handler))
    cdn = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        ref = imagegen._zai_one(api, cdn, "p", "proj", "dir", "glm-image")
    finally:
        api.close()
        cdn.close()
    assert ref is not None and ref.kind == "generated"
    assert calls["n"] == 3  # two 429s (backed off), then success


def test_zai_one_gives_up_after_persistent_429(clean_env, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"code": "1302"}})

    monkeypatch.setattr(imagegen.time, "sleep", lambda *_a, **_k: None)
    api = httpx.Client(base_url="https://api.z.ai", transport=httpx.MockTransport(handler))
    cdn = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        ref = imagegen._zai_one(api, cdn, "p", "proj", "dir", "glm-image")
    finally:
        api.close()
        cdn.close()
    assert ref is None  # exhausted -> caller falls back (regenerate / placeholder keyless)
