"""Artifact schemas — the data contracts for the whole pipeline.

Field names here are contract: later stages import these models rather than
restating them. Invariants (image provenance, hex colours, critique length,
sketch provenance) are enforced at the *model boundary* — a violating instance
is unconstructible, not merely flagged.

No heavy/optional imports at module load; this stays importable under an empty
environment (the keyless-first invariant).
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# --------------------------------------------------------------------------- #
# helpers / type aliases                                                       #
# --------------------------------------------------------------------------- #
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _blank(value: Optional[str]) -> bool:
    """True when a string is missing or whitespace-only."""
    return value is None or not str(value).strip()


ImageKind = Literal["generated", "sourced", "placeholder"]
Verdict = Literal["ship", "revise", "kill"]
DirectionStatus = Literal["draft", "promoted", "killed", "merged_away"]
# The ideator that produced a big_idea, recorded truthfully. Known values are
# "external_ideator", "claude_high_temp", "mock" — plus any configured provider label
# (IDEATOR_FALLBACK, e.g. "glm") now that generation is model-agnostic. A plain
# str, not a Literal: constraining it made every new provider a schema change.
Brain = str


# --------------------------------------------------------------------------- #
# provenance primitives                                                        #
# --------------------------------------------------------------------------- #
class SourceRef(BaseModel):
    """A research source surfaced by search."""

    title: str
    url: str
    snippet: str = ""
    query: Optional[str] = None


class ImageRef(BaseModel):
    """An image with mandatory, per-kind provenance.

    Every image tracks whether it was generated or sourced and from which
    provider. ``url`` is a path/URL — never base64 — so graph state stays lean.
    """

    kind: ImageKind
    url: str
    provider: str
    license: str
    # generated-only
    gen_model: Optional[str] = None
    gen_prompt: Optional[str] = None
    # sourced-only
    source_url: Optional[str] = None
    attribution: Optional[str] = None
    # descriptive / placeholder label
    caption: Optional[str] = None

    @field_validator("provider", "license")
    @classmethod
    def _provider_license_required(cls, v: str) -> str:
        if _blank(v):
            raise ValueError("every ImageRef needs a non-empty provider and license")
        return v

    @field_validator("url")
    @classmethod
    def _url_not_base64(cls, v: str) -> str:
        if v.strip().lower().startswith("data:"):
            raise ValueError("ImageRef.url must be a path/URL, never base64/data URI")
        return v

    @model_validator(mode="after")
    def _per_kind_provenance(self) -> "ImageRef":
        if self.kind == "generated":
            if _blank(self.gen_model) or _blank(self.gen_prompt):
                raise ValueError("generated ImageRef requires gen_model and gen_prompt")
        elif self.kind == "sourced":
            if _blank(self.source_url) or _blank(self.attribution):
                raise ValueError("sourced ImageRef requires source_url and attribution")
        return self


class Annotation(BaseModel):
    """A creative-director note attached to a direction."""

    text: str
    author: str = "human"
    at: Optional[str] = None


# --------------------------------------------------------------------------- #
# intake / research / strategy                                                 #
# --------------------------------------------------------------------------- #
class Brief(BaseModel):
    """The single plain-language brief that seeds a run (one brief per run)."""

    brief: str = Field(min_length=1)
    brand_name: str = ""
    constraints: list[str] = Field(default_factory=list)
    audience: str = ""


class CompetitorNote(BaseModel):
    name: str
    note: str
    source: Optional[SourceRef] = None


class AudienceNote(BaseModel):
    insight: str
    source: Optional[SourceRef] = None


class ResearchDossier(BaseModel):
    sources: list[SourceRef] = Field(default_factory=list)
    competitors: list[CompetitorNote] = Field(default_factory=list)
    audience_notes: list[AudienceNote] = Field(default_factory=list)
    summary: str = ""


class Strategy(BaseModel):
    positioning: str
    key_message: str
    pillars: list[str] = Field(default_factory=list)
    rationale: str = ""


class VerbalIdentity(BaseModel):
    """Candidate brand names + voice. Names are NEVER trademark-screened here
    (out of scope) — ``screened`` is a hard-coded honesty marker."""

    names: list[str] = Field(default_factory=list)
    tagline: str = ""
    tone: str = ""
    screened: Literal[False] = False


class CreativeBrief(BaseModel):
    """The written creative brief. Deliberately carries no visual/art-direction
    fields — a creative brief must not prescribe visuals."""

    objective: str
    audience: str
    key_message: str
    tone: str = ""
    mandatories: list[str] = Field(default_factory=list)


class Territory(BaseModel):
    """A strategic seed for one explored direction. ``label`` seeds mock output
    (for divergence); ``lens`` drives sketch/moodboard prompts."""

    label: str
    lens: str
    description: str = ""


# --------------------------------------------------------------------------- #
# art direction / copy                                                         #
# --------------------------------------------------------------------------- #
class PaletteColor(BaseModel):
    name: str
    hex: str
    role: str = ""

    @field_validator("hex")
    @classmethod
    def _valid_hex(cls, v: str) -> str:
        if not _HEX_RE.match(v):
            raise ValueError(f"hex must be #RRGGBB, got {v!r}")
        return v


class TypeChoice(BaseModel):
    role: str
    family: str
    fallback: str = ""
    weights: list[str] = Field(default_factory=list)


class ArtDirectionSpec(BaseModel):
    """Direction-level art direction. ``moodboard`` is empty during fan-out and
    until ``attach_visuals`` runs, after which it holds at least 4
    provenance-complete images; the exact count targets ``MOODBOARD_SIZE``
    (default 9), which the moodboard service enforces — the model only guards
    the floor of 4."""

    mood_descriptors: list[str] = Field(default_factory=list)
    imagery_direction: str
    layout_notes: str = ""
    palette: list[PaletteColor] = Field(default_factory=list)
    typography: list[TypeChoice] = Field(default_factory=list)
    moodboard: list[ImageRef] = Field(default_factory=list)

    @field_validator("moodboard")
    @classmethod
    def _moodboard_size(cls, v: list[ImageRef]) -> list[ImageRef]:
        # empty (04 stub) or at least 4 (05 floor); exact size is service-enforced.
        if v and len(v) < 4:
            raise ValueError("moodboard must hold at least 4 images when populated")
        return v


class CopyDeck(BaseModel):
    headline: str
    subhead: str = ""
    body: str = ""
    taglines: list[str] = Field(default_factory=list)
    cta: str = ""


# --------------------------------------------------------------------------- #
# critique                                                                     #
# --------------------------------------------------------------------------- #
class CritiqueScore(BaseModel):
    """Independent critic verdict, rubric v1. ``verdict`` is computed in code
; ``case_against`` must argue against the concept in ≥50 words;
    ``critic_model`` records the model that critiqued."""

    distinctiveness: int
    strategic_fit: int
    memorability: int
    audience_resonance: int
    feasibility: int
    case_against: str
    verdict: Verdict
    critic_model: str

    @field_validator(
        "distinctiveness",
        "strategic_fit",
        "memorability",
        "audience_resonance",
        "feasibility",
    )
    @classmethod
    def _score_range(cls, v: int) -> int:
        if not (1 <= v <= 5):
            raise ValueError("rubric scores are on a 1–5 scale")
        return v

    @field_validator("case_against")
    @classmethod
    def _case_against_length(cls, v: str) -> str:
        if len(v.split()) < 50:
            raise ValueError("case_against must be at least 50 words")
        return v


class IdeaReview(BaseModel):
    """One big idea for a territory, optionally with the in-house critique of it.

    Used by the ideation gate (manual mode): externally-brainstormed ideas are
    parsed into these, critiqued by the independent critic, and surfaced back so
    the operator can iterate with their external tool. Also the shape returned by
    the automatic brainstorm⇄critique loop (auto mode). ``score`` is the
    critic's 1–5 judgement; 0.0 means "not yet critiqued"."""

    territory_label: str
    big_idea: str = Field(min_length=1)
    case_for: str = ""
    case_against: str = ""
    score: float = 0.0

    @field_validator("score")
    @classmethod
    def _score_range(cls, v: float) -> float:
        if not (0.0 <= v <= 5.0):
            raise ValueError("idea score is on a 0–5 scale (0 = uncritiqued)")
        return v


# --------------------------------------------------------------------------- #
# direction / package / cost                                                   #
# --------------------------------------------------------------------------- #
def _reject_sourced_sketches(sketches: list[ImageRef]) -> list[ImageRef]:
    for s in sketches:
        if s.kind == "sourced":
            raise ValueError("sketches are always generated (or placeholder), never sourced")
    return sketches


class Direction(BaseModel):
    """One explored creative direction. ``sketches`` are AI-generated (or a
    placeholder fallback when image-gen is unavailable) — never sourced.
    ``brain`` records which ideator produced ``big_idea`` (truthfully)."""

    id: str
    territory: Territory
    big_idea: str
    brain: Brain
    art_direction: ArtDirectionSpec
    copy: CopyDeck
    sketches: list[ImageRef] = Field(default_factory=list)
    critique: Optional[CritiqueScore] = None
    critique_stale: bool = False
    divergence_score: Optional[float] = None
    status: DirectionStatus = "draft"
    annotations: list[Annotation] = Field(default_factory=list)
    # lineage
    parent_id: Optional[str] = None
    merged_from: list[str] = Field(default_factory=list)
    lens_tweak: Optional[str] = None

    _check_sketches = field_validator("sketches")(_reject_sourced_sketches)


class ConceptPackage(BaseModel):
    """The finalized, export-bound package for one promoted direction."""

    direction_id: str
    territory_label: str
    strategy: Strategy
    big_idea: str
    names: list[str] = Field(default_factory=list)
    sketches: list[ImageRef] = Field(default_factory=list)
    art_direction: ArtDirectionSpec
    copy: CopyDeck
    rationale: str

    _check_sketches = field_validator("sketches")(_reject_sourced_sketches)


class CostRecord(BaseModel):
    """One provider call's cost/usage. For image lanes, ``output_tokens``
    carries the image count."""

    agent: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


# --------------------------------------------------------------------------- #
# editable-fields / divergence-fields — the curation + divergence contract     #
# --------------------------------------------------------------------------- #
# Divergence is computed over exactly these three text fields.
DIVERGENCE_FIELDS: tuple[str, ...] = (
    "big_idea",
    "copy.headline",
    "art_direction.imagery_direction",
)

# Fields the curation gate's `edit` op may patch. A superset of DIVERGENCE_FIELDS;
# edits to a divergence field re-route through the divergence node.
EDITABLE_FIELDS: tuple[str, ...] = (
    "big_idea",
    "copy.headline",
    "copy.subhead",
    "copy.body",
    "copy.cta",
    "art_direction.imagery_direction",
    "art_direction.layout_notes",
    "art_direction.mood_descriptors",
)
