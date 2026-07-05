"""Checkpointer serde that explicitly registers our artifact types.

LangGraph's msgpack layer warns — "Deserializing unregistered type
app.models.artifacts.<X> from checkpoint. This will be blocked in a future
version." — for every artifact model it reads back from a checkpoint (any
``aget_state`` / resume). We build a serializer whose allowlist names those types
explicitly, so they're an allowed path (no warning) and we're ready for the future
strict default.

The allowlist is COMPLETE: the only non-LangGraph-safe types the graph checkpoints
are our ``app.models.artifacts`` models (they are the graph-state schema; the
interrupt payloads are plain dicts) — which is exactly why those were the only
types that ever warned. We introspect the module so a newly-added artifact can
never be forgotten from the list.
"""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from enum import Enum

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel

from app.models import artifacts


def artifact_types() -> tuple[type, ...]:
    """Every BaseModel/Enum class DEFINED in app.models.artifacts."""
    return tuple(
        obj
        for _name, obj in inspect.getmembers(artifacts, inspect.isclass)
        if obj.__module__ == artifacts.__name__ and issubclass(obj, (BaseModel, Enum))
    )


def make_serde() -> JsonPlusSerializer:
    """A JsonPlusSerializer whose msgpack allowlist names our artifact types."""
    return JsonPlusSerializer(allowed_msgpack_modules=artifact_types())


@asynccontextmanager
async def open_checkpointer(conn: str):
    """Open an ``AsyncSqliteSaver`` whose serde registers our artifact types.

    Drop-in for ``AsyncSqliteSaver.from_conn_string`` (same async-context-manager
    interface) so every checkpointer in the app/scripts/tests shares one serde.
    """
    async with AsyncSqliteSaver.from_conn_string(conn) as saver:
        saver.serde = make_serde()
        yield saver
