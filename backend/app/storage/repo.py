"""Registry, event-log, and in-process pub/sub repositories.

Narrow, swappable repos over the SQLite tables in ``db.py``:
  * ``RegistryRepo`` — project CRUD + ``list_resumable`` filtering.
  * ``EventRepo``   — atomic ``append`` (returns a per-project seq), ``since``
                      backfill, and pub/sub publish after commit.
  * ``EventBus``    — in-process fan-out; the SSE route consumes it.

Repos return view models (never live ORM rows) so callers never touch a
detached/expired instance.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Union

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.events import NON_RESUMABLE_STATES, EventType, RunState
from app.models.views import EventOut, ProjectSummary
from app.storage.db import EventRow, ProjectRow

_MAX_SEQ_RETRIES = 8


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_value(x: Union[str, RunState, EventType]) -> str:
    """Normalize an enum-or-str to its wire string (avoids ``RunState.x`` repr)."""
    return x.value if isinstance(x, (RunState, EventType)) else str(x)


def _summary(row: ProjectRow) -> ProjectSummary:
    return ProjectSummary(
        id=row.id,
        state=row.state,
        brief_excerpt=row.brief_excerpt,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class EventBus:
    """In-process pub/sub, scoped per project_id. Delivery is best-effort and
    non-blocking (``put_nowait``); SSE subscribers drain their own queue."""

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, project_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs[project_id].append(q)
        return q

    def unsubscribe(self, project_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(project_id)
        if subs and q in subs:
            subs.remove(q)
            if not subs:
                self._subs.pop(project_id, None)

    def publish(self, project_id: str, event: dict) -> None:
        for q in list(self._subs.get(project_id, ())):
            q.put_nowait(event)


class RegistryRepo:
    """Durable project registry (lifecycle state cache)."""

    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create(
        self,
        project_id: str,
        state: Union[str, RunState] = RunState.intake,
        brief_excerpt: str = "",
    ) -> ProjectSummary:
        now = _now()
        with self._sf() as s:
            row = ProjectRow(
                id=project_id,
                state=_as_value(state),
                brief_excerpt=brief_excerpt,
                error=None,
                created_at=now,
                updated_at=now,
            )
            s.add(row)
            s.commit()
            return _summary(row)

    def get(self, project_id: str) -> ProjectSummary | None:
        with self._sf() as s:
            row = s.get(ProjectRow, project_id)
            return _summary(row) if row is not None else None

    def list(self) -> list[ProjectSummary]:
        with self._sf() as s:
            rows = s.scalars(select(ProjectRow)).all()
            return [_summary(r) for r in rows]

    def update_state(
        self,
        project_id: str,
        state: Union[str, RunState],
        error: str | None = None,
    ) -> ProjectSummary | None:
        with self._sf() as s:
            row = s.get(ProjectRow, project_id)
            if row is None:
                return None
            row.state = _as_value(state)
            if error is not None:
                row.error = error
            row.updated_at = _now()
            s.commit()
            return _summary(row)

    def list_resumable(self) -> list[ProjectSummary]:
        """Projects safe to auto-resume after a restart: anything not waiting on
        a human, terminal, or never-started (``error`` IS resumable)."""
        excluded = {_as_value(x) for x in NON_RESUMABLE_STATES}
        with self._sf() as s:
            rows = s.scalars(
                select(ProjectRow).where(ProjectRow.state.not_in(excluded))
            ).all()
            return [_summary(r) for r in rows]


class EventRepo:
    """Append-only event log with per-project monotonic ``seq`` + pub/sub."""

    def __init__(self, session_factory, bus: EventBus) -> None:
        self._sf = session_factory
        self._bus = bus

    def append(self, project_id: str, type: Union[str, EventType], payload: dict) -> int:
        """Atomically append an event; returns its per-project ``seq`` (1-based).

        Concurrency-safe: ``seq`` is allocated as ``max(seq)+1`` under the unique
        ``(project_id, seq)`` constraint; a collision rolls back and retries.
        Publishes to the bus only after a successful commit.
        """
        etype = _as_value(type)
        payload = payload or {}
        for _ in range(_MAX_SEQ_RETRIES):
            at = _now()
            with self._sf() as s:
                current = s.scalar(
                    select(func.coalesce(func.max(EventRow.seq), 0)).where(
                        EventRow.project_id == project_id
                    )
                )
                seq = int(current) + 1
                s.add(
                    EventRow(
                        project_id=project_id,
                        seq=seq,
                        type=etype,
                        payload=payload,
                        at=at,
                    )
                )
                try:
                    s.commit()
                except IntegrityError:
                    s.rollback()
                    continue
            self._bus.publish(
                project_id,
                {"seq": seq, "type": etype, "payload": payload, "project_id": project_id, "at": at},
            )
            return seq
        raise RuntimeError(f"could not allocate event seq for {project_id!r}")

    def since(self, project_id: str, after_seq: int) -> list[EventOut]:
        """Events with ``seq > after_seq`` for a project, ordered by seq."""
        with self._sf() as s:
            rows = s.scalars(
                select(EventRow)
                .where(EventRow.project_id == project_id, EventRow.seq > after_seq)
                .order_by(EventRow.seq)
            ).all()
            return [EventOut(seq=r.seq, type=r.type, payload=r.payload, at=r.at) for r in rows]
