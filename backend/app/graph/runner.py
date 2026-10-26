"""RunManager — drives graph runs and projects durable state.

Owns the compiled graph and, per project, an ``asyncio.Task`` + ``asyncio.Lock``
so a run and its resume never interleave. ``start``/``resume`` spawn a task that
streams the graph and translates its two stream channels into durable events +
registry state:

  * ``custom``  chunks -> the observability event a node emitted verbatim;
  * ``updates`` chunks -> per-node completion (registry state + run_state_changed)
    or ``__interrupt__`` (gate reached; run pauses awaiting a human).

``get_view`` composes the API/SSE detail view from the registry row, the
checkpointed graph values, and the current interrupt payload.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from langgraph.types import Command

from app.models.artifacts import Brief
from app.models.events import (
    GATE_RUN_STATE,
    NODE_RUN_STATE,
    EventType,
    RunState,
)
from app.models.views import ProjectView
from app.storage.repo import EventBus, EventRepo, RegistryRepo

# gate name (as it appears in an interrupt payload) -> awaiting_* state.
_GATE_STATE: dict[str, RunState] = {
    "strategy": RunState.awaiting_strategy_approval,
    "ideation": RunState.awaiting_ideation,
    "curation": RunState.awaiting_curation,
}


class RunManager:
    def __init__(
        self,
        registry: RegistryRepo,
        events: EventRepo,
        bus: EventBus,
        checkpointer,
    ) -> None:
        from app.graph.build import build_graph

        self.registry = registry
        self.events = events
        self.bus = bus
        self.graph = build_graph(checkpointer)
        self._tasks: dict[str, asyncio.Task] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    # ------------------------------------------------------------------ #
    # config / locking helpers                                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _cfg(project_id: str) -> dict:
        return {"configurable": {"thread_id": project_id}}

    def _lock(self, project_id: str) -> asyncio.Lock:
        return self._locks[project_id]

    # ------------------------------------------------------------------ #
    # lifecycle                                                          #
    # ------------------------------------------------------------------ #
    def create(self, project_id: str, brief: Brief) -> None:
        """Register an intake row + a run_created event, without starting."""
        excerpt = brief.brief[:200]
        self.registry.create(
            project_id, state=RunState.intake, brief_excerpt=excerpt
        )
        self.events.append(
            project_id,
            EventType.run_created,
            {"project_id": project_id, "brief_excerpt": excerpt},
        )

    async def start(
        self, project_id: str, brief: Brief, ideation_mode: str = "internal"
    ) -> asyncio.Task:
        # Register only if we have not already (POST /projects may pre-create).
        if self.registry.get(project_id) is None:
            self.create(project_id, brief)
        return self._spawn(
            project_id,
            {"project_id": project_id, "brief": brief, "ideation_mode": ideation_mode},
        )

    async def resume(self, project_id: str, decision: dict) -> asyncio.Task:
        return self._spawn(project_id, Command(resume=decision))

    async def retry(self, project_id: str) -> asyncio.Task | None:
        """Re-drive an errored run from its last checkpoint (state=error only).

        Resumes with ``None`` input — LangGraph re-runs the pending (failed) node
        from the checkpoint; already-completed nodes/branches are NOT re-run
        (idempotency lives in checkpoint discipline, not ad-hoc flags)."""
        summary = self.registry.get(project_id)
        if summary is None or summary.state != RunState.error.value:
            return None
        return self._spawn(project_id, None)

    async def cancel(self, project_id: str) -> bool:
        """Cancel a project's in-flight task and mark it ``cancelled``. Idempotent;
        leaves consistent state even mid-fan-out (the last checkpoint stands, no
        orphaned task)."""
        summary = self.registry.get(project_id)
        if summary is None:
            return False
        task = self._tasks.get(project_id)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001 - a dying task must not block cancellation
                pass
        self.registry.update_state(project_id, RunState.cancelled)
        self.events.append(project_id, EventType.run_cancelled, {"project_id": project_id})
        self.events.append(project_id, EventType.run_state_changed, {"to_state": RunState.cancelled.value})
        return True

    async def resume_all(self) -> list[asyncio.Task]:
        """Re-drive every resumable run from its last checkpoint (boot recovery)."""
        return [self._spawn(row.id, None) for row in self.registry.list_resumable()]

    def _spawn(self, project_id: str, graph_input) -> asyncio.Task:
        cfg = self._cfg(project_id)
        task = asyncio.create_task(
            self._drive_locked(project_id, graph_input, cfg)
        )
        self._tasks[project_id] = task
        return task

    async def _drive_locked(self, project_id: str, graph_input, cfg) -> None:
        async with self._lock(project_id):
            await self._drive(project_id, graph_input, cfg)

    # ------------------------------------------------------------------ #
    # the stream driver                                                  #
    # ------------------------------------------------------------------ #
    async def _drive(self, project_id: str, graph_input, cfg) -> None:
        try:
            async for mode, chunk in self.graph.astream(
                graph_input,
                cfg,
                stream_mode=["updates", "custom"],
                durability="sync",
            ):
                if mode == "custom":
                    self.events.append(
                        project_id,
                        chunk["type"],
                        {k: v for k, v in chunk.items() if k != "type"},
                    )
                    continue
                # mode == "updates"
                for node, delta in chunk.items():
                    if node == "__interrupt__":
                        self._on_interrupt(project_id, delta)
                        return  # paused; stop driving
                    if node in GATE_RUN_STATE:
                        # Fires on resume when a gate node completes ("<gate>_gate").
                        self.events.append(
                            project_id,
                            EventType.gate_resolved,
                            {"gate": node.removesuffix("_gate")},
                        )
                    if node in NODE_RUN_STATE:
                        state = NODE_RUN_STATE[node]
                        self.registry.update_state(project_id, state)
                        self.events.append(
                            project_id,
                            EventType.run_state_changed,
                            {"to_state": state.value},
                        )
            # Stream drained with no interrupt -> the run finished.
            self.registry.update_state(project_id, RunState.done)
            self.events.append(
                project_id,
                EventType.run_state_changed,
                {"to_state": RunState.done.value},
            )
        except Exception as exc:  # noqa: BLE001 - surface as durable error state
            self.registry.update_state(project_id, RunState.error, error=str(exc))
            self.events.append(
                project_id,
                EventType.agent_failed,
                {"agent": "graph", "error": str(exc)},
            )
            self.events.append(
                project_id,
                EventType.run_state_changed,
                {"to_state": RunState.error.value},
            )

    def _on_interrupt(self, project_id: str, delta) -> None:
        payload = delta[0].value
        gate = payload.get("gate")
        state = _GATE_STATE.get(gate)
        if state is not None:
            self.registry.update_state(project_id, state)
        self.events.append(
            project_id,
            EventType.gate_reached,
            {"gate": gate, "payload": payload},
        )
        if state is not None:
            self.events.append(
                project_id,
                EventType.run_state_changed,
                {"to_state": state.value},
            )

    # ------------------------------------------------------------------ #
    # projection                                                         #
    # ------------------------------------------------------------------ #
    async def get_view(self, project_id: str) -> ProjectView | None:
        summary = self.registry.get(project_id)
        if summary is None:
            return None
        snap = await self.graph.aget_state(self._cfg(project_id))
        values = snap.values or {}
        interrupt = snap.interrupts[0].value if snap.interrupts else None
        return ProjectView(
            **summary.model_dump(),
            brief=values.get("brief"),
            ideation_mode=values.get("ideation_mode") or "internal",
            research=values.get("research"),
            strategy=values.get("strategy"),
            verbal_identity=values.get("verbal_identity"),
            creative_brief=values.get("creative_brief"),
            territories=values.get("territories") or [],
            directions=values.get("directions") or [],
            divergence=values.get("divergence"),
            packages=values.get("packages") or [],
            interrupt=interrupt,
        )
