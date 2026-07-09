"""Conceptial ideator client (§8.3).

Talks to the `creativity_steering` serving harness from BrainstormLM
(`creativity_steering/scripts/serve_steering.py`) — the process that loads the
steered model (Qwen2.5-32B-Instruct per BrainstormLM's docs/port_to_qwen32b.md
ship package) once and exposes it over HTTP. That harness is a raw single-
completion endpoint (`POST /generate` -> `{text, ...}`), so `generate()` calls
it once per requested idea, varying `seed` for spread, and asks the model to
answer in a `Title: ...` / `Notes: ...` format that it then parses into
`{big_idea, notes}`.

Bearer auth is sent only when `CONCEPTIAL_API_KEY` is set (the harness itself
has no auth; this is for callers fronted by an authenticating proxy); 90s
timeout, 2 transport retries. Keyless (or on failure) it raises
`ConceptialUnavailable` so the `explore_territory` node falls back to
claude_high_temp / mock — and records `brain` truthfully (never "conceptial"
for a fallback).
"""

from __future__ import annotations

import httpx

from app.config import get_settings


class ConceptialUnavailable(Exception):
    """Conceptial is not configured or the call failed — caller must fall back."""


_PROMPT_TEMPLATE = """{creative_brief}

Creative territory: {label}
Lens: {lens}

Propose ONE genuinely strong creative big idea for THIS brand and brief, grounded in the \
research and competitive context above — a substantive strategic concept a real brand team \
could build a campaign on. It must exploit the white space competitors leave open and speak \
to the audience's actual insight.

Not a gimmick. NO invented product names, NO trademarked coinages, NO sci-fi or "quantum"/ \
"neuro" jargon mash-ups — those read as clever nonsense, not ideas. The idea is a strategic \
concept expressed plainly, not a made-up brand name.

Reply in exactly this format, nothing else:
Title: <the big idea as a plain, memorable sentence — the concept, not a product name>
Notes: <2-3 sentences: how it uses the research/competitive gap and moves the audience>"""


def _territory_dict(territory) -> dict:
    if isinstance(territory, dict):
        return {"label": territory.get("label", ""), "lens": territory.get("lens", "")}
    return {"label": territory.label, "lens": territory.lens}


def _parse_idea(text: str) -> dict:
    """Split a ``Title: ...`` / ``Notes: ...`` completion into ``{big_idea, notes}``.
    Falls back to treating the whole completion as the big idea when the steered
    model doesn't follow the requested format."""
    title, notes = "", ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("title:"):
            title = stripped.split(":", 1)[1].strip()
        elif stripped.lower().startswith("notes:"):
            notes = stripped.split(":", 1)[1].strip()
    return {"big_idea": title or text.strip(), "notes": notes}


def generate(
    creative_brief: str,
    territory,
    *,
    n_ideas: int = 1,
    client: httpx.Client | None = None,
    transport: httpx.BaseTransport | None = None,
) -> list[dict]:
    """Return ``n_ideas`` ``{big_idea, notes}`` dicts from the Conceptial 32B steering
    server, issuing one ``POST /generate`` per idea (seed = its index). Raises
    ``ConceptialUnavailable`` when unconfigured or any call fails. ``client`` /
    ``transport`` are injectable for tests (``transport`` lets tests exercise the
    real client-construction path — auth header, base URL — with a MockTransport)."""
    settings = get_settings()
    if settings.conceptial_mode == "mock":
        raise ConceptialUnavailable("CONCEPTIAL_BASE_URL is not configured")

    territory_d = _territory_dict(territory)
    prompt = _PROMPT_TEMPLATE.format(
        creative_brief=creative_brief, label=territory_d["label"], lens=territory_d["lens"]
    )

    owns_client = client is None
    if client is None:
        headers = {}
        api_key = settings.CONCEPTIAL_API_KEY
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key}"
        client = httpx.Client(
            base_url=settings.CONCEPTIAL_BASE_URL,
            headers=headers,
            timeout=90.0,
            transport=transport or httpx.HTTPTransport(retries=2),
        )
    try:
        ideas: list[dict] = []
        for seed in range(n_ideas):
            body: dict = {"prompt": prompt, "seed": seed}
            if settings.CONCEPTIAL_VARIANT:
                body["variant"] = settings.CONCEPTIAL_VARIANT
            resp = client.post("/generate", json=body)
            resp.raise_for_status()
            ideas.append(_parse_idea(resp.json()["text"]))
        return ideas
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        raise ConceptialUnavailable(str(exc)) from exc
    finally:
        if owns_client:
            client.close()
