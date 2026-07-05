"""Image generation lane (§8.6).

`generate(prompts)` returns one ``kind="generated"`` ImageRef per prompt. The
mock writes placeholder PNG bytes to ``data/generated/{project_id}/{direction_id}/
{uuid}.png`` and sets ``url`` to the served path — **never base64 into state**.
Every ref carries full generated provenance (``gen_model`` + exact ``gen_prompt``
so regeneration is 1:1). Disabled (no ``IMAGE_GEN_PROVIDER``) → ``ImageGenUnavailable``.

Real fal/Replicate/OpenAI calls land in sub-plan 07; the interface is stable.
"""

from __future__ import annotations

import base64
import uuid

import httpx

from app.config import GENERATED_DIR, get_settings
from app.models.artifacts import ImageRef

# A valid 1x1 transparent PNG (real file bytes — no Pillow dependency needed).
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
URL_PREFIX = "/generated"


class ImageGenUnavailable(Exception):
    """The image-generation lane is disabled or unreachable — caller must fall back."""


def _persist_image_bytes(content: bytes, project_id: str, direction_id: str) -> str:
    """Persist image bytes and return the served URL path (never base64)."""
    dest_dir = GENERATED_DIR / project_id / direction_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.png"
    (dest_dir / name).write_bytes(content)
    return f"{URL_PREFIX}/{project_id}/{direction_id}/{name}"


def _write_placeholder_image(project_id: str, direction_id: str) -> str:
    return _persist_image_bytes(_PLACEHOLDER_PNG, project_id, direction_id)


def _mock_generate(prompts: list[str], project_id: str, direction_id: str, gen_model: str) -> list[ImageRef]:
    refs: list[ImageRef] = []
    for prompt in prompts:
        url = _write_placeholder_image(project_id, direction_id)
        refs.append(
            ImageRef(
                kind="generated",
                url=url,
                provider="generated",
                license="AI-generated",
                gen_model=gen_model,
                gen_prompt=prompt,
            )
        )
    return refs


def _fal_generate(
    prompts: list[str], *, project_id: str, direction_id: str, model: str, transport: httpx.BaseTransport | None = None
) -> list[ImageRef]:
    """Real fal.ai generation: POST prompt -> image URL -> download + persist bytes.
    The exact prompt is recorded for 1:1 regeneration. Failures raise
    ImageGenUnavailable (the caller redirects / falls back to placeholders)."""
    settings = get_settings()
    client = httpx.Client(
        base_url="https://fal.run",
        headers={"Authorization": f"Key {settings.FAL_KEY or ''}"},
        timeout=120.0,
        transport=transport,
    )
    refs: list[ImageRef] = []
    try:
        for prompt in prompts:
            resp = client.post(f"/{model}", json={"prompt": prompt})
            resp.raise_for_status()
            images = resp.json().get("images") or []
            if not images:
                raise ImageGenUnavailable("fal returned no images")
            img = client.get(images[0]["url"])
            img.raise_for_status()
            url = _persist_image_bytes(img.content, project_id, direction_id)
            refs.append(
                ImageRef(
                    kind="generated",
                    url=url,
                    provider="fal",
                    license="AI-generated",
                    gen_model=model,
                    gen_prompt=prompt,
                )
            )
        return refs
    except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError) as exc:
        raise ImageGenUnavailable(str(exc)) from exc
    finally:
        client.close()


def _openai_generate(
    prompts: list[str], *, project_id: str, direction_id: str, model: str, transport: httpx.BaseTransport | None = None
) -> list[ImageRef]:
    """OpenAI Images: POST -> b64_json -> decode + persist bytes."""
    settings = get_settings()
    client = httpx.Client(
        base_url="https://api.openai.com",
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY or ''}"},
        timeout=120.0,
        transport=transport,
    )
    refs: list[ImageRef] = []
    try:
        for prompt in prompts:
            resp = client.post(
                "/v1/images/generations",
                json={"model": model, "prompt": prompt, "n": 1, "response_format": "b64_json"},
            )
            resp.raise_for_status()
            data = resp.json().get("data") or []
            if not data:
                raise ImageGenUnavailable("openai returned no images")
            url = _persist_image_bytes(base64.b64decode(data[0]["b64_json"]), project_id, direction_id)
            refs.append(
                ImageRef(kind="generated", url=url, provider="openai", license="AI-generated", gen_model=model, gen_prompt=prompt)
            )
        return refs
    except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError) as exc:
        raise ImageGenUnavailable(str(exc)) from exc
    finally:
        client.close()


def _replicate_generate(
    prompts: list[str], *, project_id: str, direction_id: str, model: str, transport: httpx.BaseTransport | None = None
) -> list[ImageRef]:
    """Replicate: create prediction -> output URL -> download + persist bytes.
    (Real Replicate is async; a production impl polls the prediction until it
    succeeds — here we read a completed ``output`` for simplicity.)"""
    settings = get_settings()
    client = httpx.Client(
        base_url="https://api.replicate.com",
        headers={"Authorization": f"Bearer {settings.REPLICATE_API_TOKEN or ''}"},
        timeout=180.0,
        transport=transport,
    )
    refs: list[ImageRef] = []
    try:
        for prompt in prompts:
            resp = client.post("/v1/predictions", json={"version": model, "input": {"prompt": prompt}})
            resp.raise_for_status()
            output = resp.json().get("output") or []
            if not output:
                raise ImageGenUnavailable("replicate returned no output")
            img = client.get(output[0])
            img.raise_for_status()
            url = _persist_image_bytes(img.content, project_id, direction_id)
            refs.append(
                ImageRef(kind="generated", url=url, provider="replicate", license="AI-generated", gen_model=model, gen_prompt=prompt)
            )
        return refs
    except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError) as exc:
        raise ImageGenUnavailable(str(exc)) from exc
    finally:
        client.close()


def generate(prompts: list[str], *, project_id: str, direction_id: str, model: str | None = None) -> list[ImageRef]:
    settings = get_settings()
    if not settings.image_gen_enabled:
        raise ImageGenUnavailable("image generation is disabled (no IMAGE_GEN_PROVIDER)")
    provider = (settings.IMAGE_GEN_PROVIDER or "").lower()
    gen_model = model or settings.IMAGE_GEN_MODEL
    # Real adapter only when its key is present; else (and for "mock") -> placeholder bytes.
    if provider == "fal" and settings.FAL_KEY:
        return _fal_generate(prompts, project_id=project_id, direction_id=direction_id, model=gen_model)
    if provider == "openai" and settings.OPENAI_API_KEY:
        return _openai_generate(prompts, project_id=project_id, direction_id=direction_id, model=gen_model)
    if provider == "replicate" and settings.REPLICATE_API_TOKEN:
        return _replicate_generate(prompts, project_id=project_id, direction_id=direction_id, model=gen_model)
    return _mock_generate(prompts, project_id, direction_id, gen_model)
