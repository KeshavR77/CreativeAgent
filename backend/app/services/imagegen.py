"""Image generation lane.

`generate(prompts)` returns one ``kind="generated"`` ImageRef per prompt. The
mock writes placeholder PNG bytes to ``data/generated/{project_id}/{direction_id}/
{uuid}.png`` and sets ``url`` to the served path — **never base64 into state**.
Every ref carries full generated provenance (``gen_model`` + exact ``gen_prompt``
so regeneration is 1:1). Disabled (no ``IMAGE_GEN_PROVIDER``) → ``ImageGenUnavailable``.

Real fal / Replicate / OpenAI / z.ai adapters are implemented below, selected by
``IMAGE_GEN_PROVIDER``.
"""

from __future__ import annotations

import base64
import logging
import threading
import time
import uuid

import httpx

from app.config import GENERATED_DIR, get_settings
from app.models.artifacts import ImageRef

# A valid 1x1 transparent PNG (real file bytes — no Pillow dependency needed).
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
URL_PREFIX = "/generated"

logger = logging.getLogger("app.imagegen")


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


def ensure_placeholder(project_id: str, direction_id: str, filename: str) -> str:
    """Write the placeholder bytes at a DETERMINISTIC path (idempotent) and return
    its served URL. Placeholder ImageRefs must point at a file that actually
    exists — a ref to an unwritten path renders as a broken image in the UI."""
    dest_dir = GENERATED_DIR / project_id / direction_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    if not dest.exists():
        dest.write_bytes(_PLACEHOLDER_PNG)
    return f"{URL_PREFIX}/{project_id}/{direction_id}/{filename}"


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


def _zai_download(cdn: httpx.Client, url: str) -> bytes:
    """Fetch a freshly-generated image from z.ai's CDN. The URL is occasionally
    not yet propagated (observed ~1-in-10 returning 404 right after generation),
    so retry briefly before giving up on this one image."""
    last: Exception | None = None
    for attempt in range(3):
        if attempt:
            time.sleep(2.0 * attempt)
        try:
            img = cdn.get(url)
            img.raise_for_status()
            return img.content
        except httpx.HTTPError as exc:
            last = exc
    raise ImageGenUnavailable(f"z.ai CDN download failed after retries: {last}")


# z.ai's image tier rate-limits hard (HTTP 429, code 1302) and degrades under
# concurrent bursts. The parallel fan-out would otherwise fire dozens of image
# requests at once. So we SERIALIZE every z.ai image POST process-wide (one at a
# time), PACE them (a minimum gap between request starts), and BACK OFF on 429 —
# rather than hammering, which only deepens the throttle. Downloads (a different
# host, not rate-limited) happen outside the gate.
_ZAI_ATTEMPTS = 6
_ZAI_MIN_GAP = 1.5  # seconds between successive image-POST starts
_ZAI_429_BASE = 4.0  # base backoff (seconds) on a 429; exponential, capped
_ZAI_GATE = threading.Lock()
_ZAI_LAST = [0.0]  # monotonic time of the last POST start (guarded by _ZAI_GATE)


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    try:
        return float(resp.headers.get("retry-after", ""))
    except (TypeError, ValueError):
        return None


def _zai_pace() -> None:
    """Sleep so successive requests are >= _ZAI_MIN_GAP apart. Call under _ZAI_GATE."""
    gap = _ZAI_MIN_GAP - (time.monotonic() - _ZAI_LAST[0])
    if gap > 0:
        time.sleep(gap)
    _ZAI_LAST[0] = time.monotonic()


def _zai_one(
    api: httpx.Client, cdn: httpx.Client, prompt: str, project_id: str, direction_id: str, model: str
) -> ImageRef | None:
    """Generate ONE image with paced, serialized POSTs and proper 429 backoff.
    Returns a provenance-complete ref, or None if every attempt failed."""
    for attempt in range(_ZAI_ATTEMPTS):
        remote_url: str | None = None
        # --- rate-limited POST: serialized + paced across all branches ---
        with _ZAI_GATE:
            _zai_pace()
            try:
                resp = api.post(
                    "/api/paas/v4/images/generations",
                    json={"model": model, "prompt": prompt, "size": "1024x1024"},
                )
                if resp.status_code == 429:
                    backoff = _retry_after_seconds(resp) or min(_ZAI_429_BASE * (2**attempt), 30.0)
                    logger.warning(
                        "z.ai 429 rate limit; backing off %.0fs (attempt %d/%d)", backoff, attempt + 1, _ZAI_ATTEMPTS
                    )
                    time.sleep(backoff)  # held under the gate: pause ALL branches while throttled
                    continue
                resp.raise_for_status()
                data = resp.json().get("data") or []
                if not data:
                    raise ImageGenUnavailable("z.ai returned no images")
                remote_url = data[0]["url"]
            except (httpx.HTTPError, ImageGenUnavailable, KeyError, ValueError, TypeError, IndexError) as exc:
                logger.warning("zai image POST attempt %d/%d failed (%s)", attempt + 1, _ZAI_ATTEMPTS, exc)
                time.sleep(min(2.0 * (attempt + 1), 12.0))
                continue
        # --- download outside the gate (different host, not the rate-limited API) ---
        try:
            content = _zai_download(cdn, remote_url)
        except ImageGenUnavailable as exc:
            logger.warning("zai image download attempt %d/%d failed (%s)", attempt + 1, _ZAI_ATTEMPTS, exc)
            continue
        url = _persist_image_bytes(content, project_id, direction_id)
        return ImageRef(
            kind="generated", url=url, provider="zai", license="AI-generated", gen_model=model, gen_prompt=prompt
        )
    return None


def _zai_generate(
    prompts: list[str], *, project_id: str, direction_id: str, model: str, transport: httpx.BaseTransport | None = None
) -> list[ImageRef]:
    """z.ai (Zhipu) images: POST -> image URL -> download + persist bytes.
    Reuses the GLM key (one-key setups) — see Settings.zai_image_key.

    Each image is retried hard (_ZAI_ATTEMPTS) so the batch returns a real image
    for (almost) every prompt — the caller regenerates any residual shortfall, so
    a real run shows NO placeholders. Raises ImageGenUnavailable only when EVERY
    prompt failed every attempt (a genuine lane outage). The CDN download uses an
    unauthenticated client — the API key must not leak to a different host."""
    settings = get_settings()
    api = httpx.Client(
        base_url="https://api.z.ai",
        headers={"Authorization": f"Bearer {settings.zai_image_key or ''}"},
        timeout=120.0,
        transport=transport,
    )
    cdn = httpx.Client(timeout=60.0, transport=transport)  # no auth header cross-host
    try:
        refs = [
            ref
            for prompt in prompts
            if (ref := _zai_one(api, cdn, prompt, project_id, direction_id, model)) is not None
        ]
        if refs:
            return refs
        raise ImageGenUnavailable(f"z.ai produced no images for {len(prompts)} prompt(s)")
    finally:
        api.close()
        cdn.close()


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
    if provider == "zai" and settings.zai_image_key:
        return _zai_generate(prompts, project_id=project_id, direction_id=direction_id, model=gen_model)
    return _mock_generate(prompts, project_id, direction_id, gen_model)


def generate_reliable(
    prompts: list[str], *, project_id: str, direction_id: str, model: str | None = None, rounds: int = 2
) -> list[ImageRef]:
    """Return EXACTLY ``len(prompts)`` generated refs when the lane is enabled.

    Regenerates any residual shortfall across ``rounds`` (each image is already
    retried inside the adapter). As an absolute last resort under a partial outage
    it repeats a successful image rather than emitting a placeholder — so a real
    run never shows a placeholder tile. Raises ``ImageGenUnavailable`` only when
    the lane is disabled (the keyless path, where the caller uses placeholders).
    """
    want = len(prompts)
    refs = list(generate(prompts, project_id=project_id, direction_id=direction_id, model=model))
    attempts = 0
    while len(refs) < want and attempts < rounds:
        need = want - len(refs)
        try:
            refs.extend(
                generate(prompts[:need], project_id=project_id, direction_id=direction_id, model=model)
            )
        except ImageGenUnavailable:
            break
        attempts += 1
    if refs and len(refs) < want:
        logger.warning("image lane under-delivered (%d/%d); repeating real images to avoid placeholders", len(refs), want)
        i = 0
        while len(refs) < want:
            refs.append(refs[i % len(refs)])
            i += 1
    return refs[:want]
