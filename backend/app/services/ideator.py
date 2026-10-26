"""External ideator client — an optional dedicated ideation service.

`generate(creative_brief, territory)` POSTs to ``{IDEATOR_BASE_URL}/generate``
and returns a list of ``{big_idea, notes}``. Bearer auth when ``IDEATOR_API_KEY``
is set; 90s timeout, 2 transport retries. Keyless (or on failure) it raises
``IdeatorUnavailable`` so the ``explore_territory`` node falls back to
claude_high_temp / mock — and records ``brain`` truthfully (never
"external_ideator" for a fallback).

Any service that accepts that request shape and returns ``{"ideas": [...]}``
works; point ``IDEATOR_BASE_URL`` at it.
"""

from __future__ import annotations

import httpx

from app.config import get_settings


class IdeatorUnavailable(Exception):
    """The external ideator is unconfigured or the call failed — caller must fall back."""


def _territory_dict(territory) -> dict:
    if isinstance(territory, dict):
        return {"label": territory.get("label", ""), "lens": territory.get("lens", "")}
    return {"label": territory.label, "lens": territory.lens}


def generate(
    creative_brief: str,
    territory,
    *,
    n_ideas: int = 1,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> list[dict]:
    """Return ``n_ideas`` ``{big_idea, notes}`` dicts from the ideator. Raises
    ``IdeatorUnavailable`` when unconfigured or the server errors. ``client`` /
    ``transport`` are injectable for tests (``transport`` lets tests exercise the
    real client-construction path — auth header, base URL — with a MockTransport)."""
    settings = get_settings()
    if settings.ideator_mode == "mock":
        raise IdeatorUnavailable("IDEATOR_BASE_URL is not configured")

    owns_client = client is None
    if client is None:
        headers = {}
        api_key = settings.IDEATOR_API_KEY
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key}"
        client = httpx.Client(
            base_url=settings.IDEATOR_BASE_URL,
            headers=headers,
            timeout=90.0,
            transport=transport or httpx.HTTPTransport(retries=2),
        )
    try:
        resp = client.post(
            "/generate",
            json={
                "creative_brief": creative_brief,
                "territory": _territory_dict(territory),
                "n_ideas": n_ideas,
                "params": {},
            },
        )
        resp.raise_for_status()
        return list(resp.json()["ideas"])
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        raise IdeatorUnavailable(str(exc)) from exc
    finally:
        if owns_client:
            client.close()
