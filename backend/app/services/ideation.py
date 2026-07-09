"""Ideation support (§ideation modes): parse externally-brainstormed ideas and
critique ideas with the independent critic.

Used by the ideation gate (manual mode: the operator downloads an ideation
packet, brainstorms with any external creative LLM/agent, pastes the output
back) and by the automatic brainstorm⇄critique loop (conceptial mode).

Keyless-first: the critic resolves to the deterministic mock with no keys, and
parsing prefers the packet's documented format (pure text processing) with an
LLM fallback only for freeform pastes.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.models.artifacts import IdeaReview, Strategy, Territory
from app.services.mock_chat import _phrase, register_builder
from app.services.models import generate_structured, get_chat_model
from app.services.prompts import render_prompt

# Ideas below this critic score get another brainstorm round (conceptial mode).
IDEA_SCORE_BAR = 4.0


# --------------------------------------------------------------------------- #
# structured-output schemas                                                    #
# --------------------------------------------------------------------------- #
class IdeaCritiqueResult(BaseModel):
    """The critic's judgement of one big idea."""

    case_for: str = ""
    case_against: str = ""
    score: float = Field(default=3.0, ge=1.0, le=5.0)


class ParsedIdea(BaseModel):
    territory_label: str = ""
    big_idea: str = ""


class ParsedIdeas(BaseModel):
    """LLM-parse fallback container for freeform external-tool output."""

    ideas: list[ParsedIdea] = Field(default_factory=list)


def _build_idea_critique(seed: str) -> BaseModel:
    """Mock builder: a deterministic mid score (below IDEA_SCORE_BAR) so the
    keyless path exercises the regenerate round of the brainstorm⇄critique loop."""
    return IdeaCritiqueResult(
        case_for=_phrase(f"{seed}:for", 12),
        case_against=_phrase(f"{seed}:against", 14),
        score=3.2,
    )


register_builder(IdeaCritiqueResult, _build_idea_critique)


# --------------------------------------------------------------------------- #
# parsing externally-brainstormed ideas                                        #
# --------------------------------------------------------------------------- #
_HEADING = re.compile(r"^#{2,4}\s+(.+?)\s*$", re.MULTILINE)


def _format_parse(text: str) -> list[tuple[str, str]]:
    """Parse the packet's documented return format: a `### <territory>` heading
    per idea, body = the idea. Returns (heading, body) pairs in order."""
    matches = list(_HEADING.finditer(text))
    pairs: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end() : body_end].strip()
        if body:
            pairs.append((m.group(1).strip(), body))
    return pairs


def parse_external_ideas(
    text: str, territories: list[Territory], *, project_id: str = ""
) -> list[IdeaReview]:
    """Turn pasted external-tool output into per-territory ideas.

    Strategy: the documented `### <territory>` format parses deterministically
    (no model call). Headings are matched to territories case-insensitively;
    unmatched ideas are assigned to unmatched territories in order (external
    tools rename things). If nothing parses, fall back to an LLM parse of the
    freeform text. Multiple ideas per territory are allowed — the best-scored
    one wins at explore time."""
    labels = {t.label.casefold(): t.label for t in territories}
    pairs = _format_parse(text)

    if not pairs:
        # Freeform paste: let the reasoning model structure it.
        model = get_chat_model("idea_parse", project_id=project_id, temperature=0.0)
        prompt = (
            "Extract every distinct big idea from the brainstorm output below. "
            "Match each to one of these creative territories: "
            + ", ".join(t.label for t in territories)
            + ". Return JSON matching the schema (territory_label, big_idea per idea).\n\n"
            + text[:16_000]
        )
        parsed = generate_structured(model, prompt, ParsedIdeas)
        pairs = [(p.territory_label, p.big_idea) for p in parsed.ideas if p.big_idea.strip()]

    matched: list[IdeaReview] = []
    unmatched: list[str] = []
    for heading, body in pairs:
        label = labels.get(heading.casefold())
        if label is not None:
            matched.append(IdeaReview(territory_label=label, big_idea=body))
        else:
            unmatched.append(body)

    # Assign leftovers to territories that received nothing, in order.
    covered = {r.territory_label for r in matched}
    for t in territories:
        if not unmatched:
            break
        if t.label not in covered:
            matched.append(IdeaReview(territory_label=t.label, big_idea=unmatched.pop(0)))
            covered.add(t.label)
    return matched


# --------------------------------------------------------------------------- #
# critiquing ideas                                                             #
# --------------------------------------------------------------------------- #
def critique_idea(
    project_id: str,
    territory_label: str,
    big_idea: str,
    *,
    strategy: Strategy | None = None,
) -> IdeaCritiqueResult:
    """One independent critic pass over one big idea (distinct model from the
    generator — same independence rule as the direction critic)."""
    model = get_chat_model("critic", project_id=project_id, temperature=0.3, seed_extra=f"idea:{territory_label}")
    prompt = render_prompt(
        "idea_critique",
        territory=territory_label,
        strategy=(strategy.positioning if strategy is not None else ""),
        big_idea=big_idea,
    )
    return generate_structured(model, prompt, IdeaCritiqueResult)


def review_ideas(
    project_id: str,
    ideas: list[IdeaReview],
    *,
    strategy: Strategy | None = None,
) -> list[IdeaReview]:
    """Critique each idea, returning reviews with case_for/case_against/score."""
    reviews: list[IdeaReview] = []
    for idea in ideas:
        crit = critique_idea(project_id, idea.territory_label, idea.big_idea, strategy=strategy)
        reviews.append(
            idea.model_copy(
                update={"case_for": crit.case_for, "case_against": crit.case_against, "score": crit.score}
            )
        )
    return reviews


def best_idea_per_territory(reviews: list[IdeaReview]) -> dict[str, str]:
    """territory_label -> the highest-scored big idea (uncritiqued ideas score 0,
    so any critiqued idea beats them; ties keep the first submitted)."""
    best: dict[str, IdeaReview] = {}
    for r in reviews:
        cur = best.get(r.territory_label)
        if cur is None or r.score > cur.score:
            best[r.territory_label] = r
    return {label: r.big_idea for label, r in best.items()}
