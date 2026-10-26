"""Real image-provider adapter tests.

Provenance mapping is pure (fixtures); the fal HTTP path uses a MockTransport (no
network, no real keys). A real provider only activates when its key is present —
otherwise the lane stays on the mock (so the keyless suite stays green).
"""

from __future__ import annotations

import base64

import httpx
import pytest

from app.services import imagegen, imagesource
from app.services import search as search_svc


# --------------------------------------------------------------------------- #
# sourced provenance mapping (pure)                                            #
# --------------------------------------------------------------------------- #
def test_pexels_maps_to_sourced_provenance(clean_env) -> None:
    payload = {
        "photos": [
            {"url": "https://pexels.com/photo/1", "photographer": "Ada Lin", "alt": "a runner", "src": {"large": "https://pexels.com/img/1.jpg"}},
            {"url": "https://pexels.com/photo/2", "photographer": "Ben Ortiz", "alt": "a shoe", "src": {"large": "https://pexels.com/img/2.jpg"}},
        ]
    }
    refs = imagesource.pexels_to_refs(payload, 5)
    assert len(refs) == 2
    for r in refs:
        assert r.kind == "sourced" and r.provider == "pexels" and r.license == "Pexels License"
        assert r.source_url and r.attribution
    assert refs[0].attribution == "Ada Lin" and refs[0].url == "https://pexels.com/img/1.jpg"


def test_unsplash_maps_to_sourced_provenance(clean_env) -> None:
    payload = {
        "results": [
            {"urls": {"regular": "https://unsplash.com/img/1.jpg"}, "links": {"html": "https://unsplash.com/photos/1"}, "user": {"name": "Gio Marchetti"}, "alt_description": "dawn trail"}
        ]
    }
    refs = imagesource.unsplash_to_refs(payload, 5)
    assert len(refs) == 1 and refs[0].kind == "sourced"
    assert refs[0].provider == "unsplash" and refs[0].license == "Unsplash License"
    assert refs[0].attribution == "Gio Marchetti"


def test_pexels_drops_provenance_incomplete_photo(clean_env) -> None:
    payload = {"photos": [{"src": {"large": "https://x/1.jpg"}, "url": "https://x/p1"}]}  # no photographer
    assert imagesource.pexels_to_refs(payload, 5) == []  # incomplete -> dropped


# --------------------------------------------------------------------------- #
# fal generation (mocked transport: POST -> image url -> download + persist)    #
# --------------------------------------------------------------------------- #
def test_fal_generate_produces_generated_provenance(clean_env) -> None:
    clean_env.setenv("FAL_KEY", "fal-test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"images": [{"url": "https://fal.media/out.png"}]})
        return httpx.Response(200, content=b"\x89PNG\r\n\x1a\n fake-bytes")

    refs = imagegen._fal_generate(
        ["a rough marker sketch of a shoe"],
        project_id="p",
        direction_id="d",
        model="flux/schnell",
        transport=httpx.MockTransport(handler),
    )
    assert len(refs) == 1
    r = refs[0]
    assert r.kind == "generated" and r.provider == "fal" and r.license == "AI-generated"
    assert r.gen_model == "flux/schnell"
    assert r.gen_prompt == "a rough marker sketch of a shoe"  # exact prompt for 1:1 regen
    assert r.url.startswith("/generated/p/d/") and not r.url.startswith("data:")


def test_fal_generate_raises_on_error(clean_env) -> None:
    clean_env.setenv("FAL_KEY", "fal-test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(imagegen.ImageGenUnavailable):
        imagegen._fal_generate(["x"], project_id="p", direction_id="d", model="m", transport=httpx.MockTransport(handler))


# --------------------------------------------------------------------------- #
# key-guarded dispatch: real provider only with its key, else mock             #
# --------------------------------------------------------------------------- #
def test_gen_provider_falls_back_to_mock_without_key(clean_env) -> None:
    clean_env.setenv("IMAGE_GEN_PROVIDER", "fal")  # no FAL_KEY -> mock placeholder path
    refs = imagegen.generate(["x", "y"], project_id="p", direction_id="d")
    assert all(r.provider == "generated" for r in refs)  # mock, not fal


def test_source_provider_falls_back_to_mock_without_key(clean_env) -> None:
    clean_env.setenv("IMAGE_SOURCE_PROVIDER", "pexels")  # no PEXELS_API_KEY -> mock corpus
    refs = imagesource.search("sneaker", 2)
    assert refs and all(r.provider.startswith("mock") for r in refs)  # bundled corpus providers


def test_openai_generate_produces_generated_provenance(clean_env) -> None:
    clean_env.setenv("OPENAI_API_KEY", "openai-test-key")
    png_b64 = base64.b64encode(b"\x89PNG fake").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"b64_json": png_b64}]})

    refs = imagegen._openai_generate(
        ["a shoe sketch"], project_id="p", direction_id="d", model="gpt-image-1", transport=httpx.MockTransport(handler)
    )
    assert refs[0].kind == "generated" and refs[0].provider == "openai"
    assert refs[0].gen_prompt == "a shoe sketch" and refs[0].url.startswith("/generated/p/d/")


def test_replicate_generate_produces_generated_provenance(clean_env) -> None:
    clean_env.setenv("REPLICATE_API_TOKEN", "r8-test")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"output": ["https://replicate.delivery/out.png"]})
        return httpx.Response(200, content=b"\x89PNG fake")

    refs = imagegen._replicate_generate(
        ["a shoe"], project_id="p", direction_id="d", model="ver123", transport=httpx.MockTransport(handler)
    )
    assert refs[0].kind == "generated" and refs[0].provider == "replicate"
    assert refs[0].url.startswith("/generated/p/d/")


# --------------------------------------------------------------------------- #
# Tavily real search (fetched web text truncated before entering state)        #
# --------------------------------------------------------------------------- #
def test_tavily_maps_and_truncates(clean_env) -> None:
    payload = {
        "results": [
            {"title": "T1", "url": "https://e/1", "content": "x" * 2000},
            {"title": "T2", "url": "https://e/2", "content": "short"},
        ]
    }
    sources = search_svc.tavily_to_sources(payload, "greenwashing", 5)
    assert len(sources) == 2
    assert sources[0].query == "greenwashing"
    assert len(sources[0].snippet) <= 500  # truncated (no full page in state)
    assert sources[1].snippet == "short"


def test_tavily_real_search_via_transport(clean_env) -> None:
    clean_env.setenv("TAVILY_API_KEY", "tvly-test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"title": "T", "url": "https://e/1", "content": "web text"}]})

    sources = search_svc._real_search("greenwashing", 4, transport=httpx.MockTransport(handler))
    assert sources[0].title == "T" and sources[0].snippet == "web text"


def test_tavily_real_search_degrades_to_mock_on_failure(clean_env) -> None:
    """A failing/slow Tavily must not fail the run — degrade to the mock corpus."""
    clean_env.setenv("TAVILY_API_KEY", "tvly-test")

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("tavily unreachable")

    sources = search_svc._real_search("sustainable sneaker greenwashing", 4, transport=httpx.MockTransport(boom))
    assert sources and all(s.url for s in sources)  # deterministic mock corpus, run continues
