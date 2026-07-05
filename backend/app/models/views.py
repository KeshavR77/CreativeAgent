"""View models — API/SSE response shapes (§6.3, §13).

`ProjectSummary` is the registry-row projection used by list endpoints.
`ProjectView` is the composed detail view (registry row + graph-state values +
current interrupt payload) assembled in sub-plan 03. `EventOut` is the event-log
/ SSE serialization shape returned by `EventRepo.since`.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.artifacts import (
    Brief,
    ConceptPackage,
    CreativeBrief,
    Direction,
    Strategy,
    Territory,
    VerbalIdentity,
)


class ProjectSummary(BaseModel):
    """Registry-row projection (list rows). `state` is a `RunState` value."""

    id: str
    state: str
    brief_excerpt: str = ""
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EventOut(BaseModel):
    """One event-log entry (`seq` doubles as the SSE `id:`)."""

    seq: int
    type: str
    payload: dict = Field(default_factory=dict)
    at: Optional[str] = None


class ProjectView(ProjectSummary):
    """Composed detail view: summary + graph-state projection + interrupt.

    Graph-state fields are optional — present only once the run has produced
    them. `interrupt` carries the current gate's payload while a run is paused.
    """

    brief: Optional[Brief] = None
    strategy: Optional[Strategy] = None
    verbal_identity: Optional[VerbalIdentity] = None
    creative_brief: Optional[CreativeBrief] = None
    territories: list[Territory] = Field(default_factory=list)
    directions: list[Direction] = Field(default_factory=list)
    divergence: Optional[dict] = None
    packages: list[ConceptPackage] = Field(default_factory=list)
    interrupt: Optional[dict] = None
