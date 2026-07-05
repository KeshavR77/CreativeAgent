"""Server-Sent Events stream for a project (§13, sub-plan 03).

``GET /api/projects/{id}/events`` replays the durable event log from
``Last-Event-ID`` (a per-project ``seq``; default 0) and then tails live events
off the in-process ``EventBus``. Frames follow the SSE wire format:

    id: {seq}
    event: {type}
    data: {json}

with a ``: heartbeat`` comment every 15s so idle proxies keep the connection
open. The subscriber is registered BEFORE backfill and de-duplicated by ``seq``
so no event is dropped or delivered twice across the backfill/live handoff; it is
always unsubscribed on disconnect.

Hand-rolled on Starlette's ``StreamingResponse`` (no ``sse-starlette`` dep).
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

router = APIRouter(prefix="/api")

_HEARTBEAT_SECONDS = 15.0


def _frame(seq: int, type_: str, payload: dict) -> str:
    return f"id: {seq}\nevent: {type_}\ndata: {json.dumps(payload)}\n\n"


@router.get("/projects/{project_id}/events")
async def project_events(project_id: str, request: Request) -> StreamingResponse:
    events = request.app.state.events
    bus = request.app.state.bus

    # Resume cursor: the native EventSource sends the `Last-Event-ID` header on
    # auto-reconnect; a client that re-creates the stream (our SSE wrapper) sends
    # `?lastEventId=` instead. Honor either, so reconnects resume from `seq` rather
    # than replaying the whole log.
    raw = request.query_params.get("lastEventId") or request.headers.get("Last-Event-ID") or "0"
    try:
        last_id = int(raw)
    except (TypeError, ValueError):
        last_id = 0

    async def gen():
        # Subscribe first so nothing appended during backfill is lost; the seq
        # high-water mark then filters duplicates out of the live queue.
        queue = bus.subscribe(project_id)
        try:
            sent_seq = last_id
            for ev in events.since(project_id, last_id):
                sent_seq = max(sent_seq, ev.seq)
                yield _frame(ev.seq, ev.type, ev.payload or {})

            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(
                        queue.get(), timeout=_HEARTBEAT_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                seq = ev.get("seq", 0)
                if seq <= sent_seq:
                    continue  # already delivered during backfill
                sent_seq = seq
                yield _frame(seq, ev.get("type", ""), ev.get("payload") or {})
        finally:
            bus.unsubscribe(project_id, queue)

    return StreamingResponse(gen(), media_type="text/event-stream")
