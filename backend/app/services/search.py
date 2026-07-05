"""Search service (§8.1, Tavily interface).

Keyless (no `TAVILY_API_KEY`) it is backed by the bundled `mock_search_corpus.json`,
returning deterministic `SourceRef`s ranked by term overlap. The real Tavily
client lands in sub-plan 07; the interface is stable so callers never change.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from app.config import get_settings
from app.models.artifacts import SourceRef

logger = logging.getLogger(__name__)

# Truncate fetched web text before it enters graph state (never full pages, §5/§19).
_MAX_SNIPPET_CHARS = 500

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "resources" / "mock_search_corpus.json"


def _load_corpus() -> list[dict]:
    return json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


def _mock_search(query: str, k: int) -> list[SourceRef]:
    corpus = _load_corpus()
    terms = set(query.lower().split())
    scored: list[tuple[int, dict]] = []
    for entry in corpus:
        hay = f"{entry.get('query', '')} {entry.get('title', '')} {entry.get('snippet', '')}".lower()
        overlap = len(terms & set(hay.split()))
        scored.append((overlap, entry))
    # deterministic: most-overlapping first, ties broken by url
    scored.sort(key=lambda t: (-t[0], t[1].get("url", "")))
    return [
        SourceRef(
            title=e["title"],
            url=e["url"],
            snippet=e.get("snippet", ""),
            query=e.get("query"),
        )
        for _, e in scored[:k]
    ]


def tavily_to_sources(payload: dict, query: str, k: int) -> list[SourceRef]:
    """Map a Tavily /search response to SourceRefs, truncating fetched text so no
    full web page enters state (§19)."""
    sources: list[SourceRef] = []
    for result in payload.get("results", [])[:k]:
        sources.append(
            SourceRef(
                title=result.get("title", ""),
                url=result.get("url", ""),
                snippet=(result.get("content", "") or "")[:_MAX_SNIPPET_CHARS],
                query=query,
            )
        )
    return sources


def _real_search(query: str, k: int, *, transport: httpx.BaseTransport | None = None) -> list[SourceRef]:
    settings = get_settings()
    # Bounded timeout (a slow Tavily must never stall the research node) + transport
    # retries for transient connect failures. Tests inject their own transport.
    client = httpx.Client(
        base_url="https://api.tavily.com",
        timeout=httpx.Timeout(20.0, connect=5.0),
        transport=transport or httpx.HTTPTransport(retries=2),
    )
    try:
        resp = client.post(
            "/search",
            json={"api_key": settings.TAVILY_API_KEY, "query": query, "max_results": k},
        )
        resp.raise_for_status()
        return tavily_to_sources(resp.json(), query, k)
    except (httpx.HTTPError, ValueError) as exc:
        # Degrade gracefully (§ hardening): a failing/slow/malformed Tavily must not
        # fail the run — fall back to the deterministic mock corpus and keep going.
        logger.warning("Tavily search failed (%s); falling back to mock corpus", exc)
        return _mock_search(query, k)
    finally:
        client.close()


def search(query: str, *, k: int = 4) -> list[SourceRef]:
    """Return up to `k` sources for `query`. Mock-backed when keyless."""
    if get_settings().search_mode == "mock":
        return _mock_search(query, k)
    return _real_search(query, k)
