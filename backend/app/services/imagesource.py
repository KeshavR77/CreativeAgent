"""Image sourcing lane.

`search(query, n)` returns up to ``n`` ``kind="sourced"`` ImageRefs from the
bundled corpus, ranked by query/tag overlap, each with full sourced provenance
(``provider``, ``license``, ``source_url``, ``attribution``). Corpus entries that
can't form a provenance-complete ref are dropped (never surface an image without
provenance). Disabled (no ``IMAGE_SOURCE_PROVIDER``) → ``ImageSourceUnavailable``.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.config import get_settings
from app.models.artifacts import ImageRef

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "resources" / "mock_image_corpus.json"


class ImageSourceUnavailable(Exception):
    """The image-sourcing lane is disabled or unreachable — caller must fall back."""


def _load_corpus() -> list[dict]:
    return json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


def _rank(corpus: list[dict], query: str) -> list[dict]:
    terms = set(query.lower().split())
    scored: list[tuple[int, dict]] = []
    for entry in corpus:
        hay = f"{entry.get('description', '')} {' '.join(entry.get('tags', []))}".lower()
        overlap = len(terms & set(hay.split()))
        scored.append((overlap, entry))
    scored.sort(key=lambda t: (-t[0], t[1]["id"]))  # deterministic
    return [entry for _, entry in scored]


def _to_ref(entry: dict) -> ImageRef | None:
    """Build a sourced ImageRef, or None if the entry lacks complete provenance."""
    try:
        return ImageRef(
            kind="sourced",
            url=entry["url"],
            provider=entry["provider"],
            license=entry["license"],
            source_url=entry["source_url"],
            attribution=entry["attribution"],
            caption=entry.get("description"),
        )
    except (KeyError, ValueError):
        return None


def search(query: str, n: int) -> list[ImageRef]:
    settings = get_settings()
    if not settings.image_source_enabled:
        raise ImageSourceUnavailable("image sourcing is disabled (no IMAGE_SOURCE_PROVIDER)")
    provider = (settings.IMAGE_SOURCE_PROVIDER or "").lower()
    # Real adapters activate only when the matching key is present; otherwise (and
    # for the "mock" provider) we serve the bundled corpus so mock-first stays green.
    if provider == "pexels" and settings.PEXELS_API_KEY:
        return _pexels_search(query, n)
    if provider == "unsplash" and settings.UNSPLASH_ACCESS_KEY:
        return _unsplash_search(query, n)
    return _mock_search(query, n)


def _mock_search(query: str, n: int) -> list[ImageRef]:
    refs: list[ImageRef] = []
    for entry in _rank(_load_corpus(), query):
        if len(refs) >= n:
            break
        ref = _to_ref(entry)
        if ref is not None:
            refs.append(ref)
    return refs


# --------------------------------------------------------------------------- #
# real adapters — provenance mapping is pure + unit-tested; HTTP wrappers #
# stay thin. Transient failures raise ImageSourceUnavailable (lane fallback).   #
# --------------------------------------------------------------------------- #
def pexels_to_refs(payload: dict, n: int) -> list[ImageRef]:
    refs: list[ImageRef] = []
    for photo in payload.get("photos", [])[:n]:
        src = photo.get("src", {}) or {}
        ref = _to_ref(
            {
                "url": src.get("large") or src.get("original") or photo.get("url", ""),
                "provider": "pexels",
                "license": "Pexels License",
                "source_url": photo.get("url", ""),
                "attribution": photo.get("photographer", ""),
                "description": photo.get("alt", ""),
            }
        )
        if ref is not None:
            refs.append(ref)
    return refs


def _pexels_search(query: str, n: int, *, transport: httpx.BaseTransport | None = None) -> list[ImageRef]:
    settings = get_settings()
    client = httpx.Client(
        base_url="https://api.pexels.com",
        headers={"Authorization": settings.PEXELS_API_KEY or ""},
        timeout=30.0,
        transport=transport,
    )
    try:
        resp = client.get("/v1/search", params={"query": query, "per_page": n})
        resp.raise_for_status()
        return pexels_to_refs(resp.json(), n)
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        raise ImageSourceUnavailable(str(exc)) from exc
    finally:
        client.close()


def unsplash_to_refs(payload: dict, n: int) -> list[ImageRef]:
    refs: list[ImageRef] = []
    for photo in payload.get("results", [])[:n]:
        ref = _to_ref(
            {
                "url": (photo.get("urls", {}) or {}).get("regular", ""),
                "provider": "unsplash",
                "license": "Unsplash License",
                "source_url": (photo.get("links", {}) or {}).get("html", ""),
                "attribution": (photo.get("user", {}) or {}).get("name", ""),
                "description": photo.get("alt_description", ""),
            }
        )
        if ref is not None:
            refs.append(ref)
    return refs


def _unsplash_search(query: str, n: int, *, transport: httpx.BaseTransport | None = None) -> list[ImageRef]:
    settings = get_settings()
    client = httpx.Client(
        base_url="https://api.unsplash.com",
        headers={"Authorization": f"Client-ID {settings.UNSPLASH_ACCESS_KEY or ''}"},
        timeout=30.0,
        transport=transport,
    )
    try:
        resp = client.get("/search/photos", params={"query": query, "per_page": n})
        resp.raise_for_status()
        return unsplash_to_refs(resp.json(), n)
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        raise ImageSourceUnavailable(str(exc)) from exc
    finally:
        client.close()
