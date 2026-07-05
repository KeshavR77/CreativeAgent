"""SQLite engine + ORM tables (§7).

SQLAlchemy 2.0 typed models. Two tables:
  projects(id PK, state, brief_excerpt, error, created_at, updated_at)
  events(id PK AUTOINC, project_id, seq, type, payload JSON, at) UNIQUE(project_id, seq)

`data/` is auto-created (and gitignored). Repos stay narrow so a Postgres engine
(+ LangGraph `PostgresSaver`) can swap in later — nothing here is SQLite-specific
beyond the default URL.

Note: this module intentionally does NOT use `from __future__ import annotations`;
SQLAlchemy's `Mapped[...]` resolution is most reliable with real annotations.
"""

from pathlib import Path
from typing import Optional

from sqlalchemy import JSON, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

_DATA_DIR = Path("data")
_SQLITE_PREFIX = "sqlite:///"


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    state: Mapped[str] = mapped_column(String, index=True)
    brief_excerpt: Mapped[str] = mapped_column(String, default="")
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("project_id", "seq", name="uq_events_project_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[str] = mapped_column(String)


def _ensure_sqlite_dir(url: str) -> None:
    """Create the parent directory of a file-backed SQLite DB if needed."""
    if not url.startswith(_SQLITE_PREFIX):
        return
    path = url[len(_SQLITE_PREFIX) :]
    if path and path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def make_engine(url: Optional[str] = None) -> Engine:
    """Build an Engine. Defaults to a file DB under ``data/`` (auto-created)."""
    if url is None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        url = f"{_SQLITE_PREFIX}{_DATA_DIR / 'app.db'}"
    _ensure_sqlite_dir(url)
    return create_engine(url)


def make_sessionmaker(engine: Engine) -> sessionmaker:
    """Session factory. ``expire_on_commit=False`` so repos can project rows to
    view models after commit within the same block."""
    return sessionmaker(engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Create tables if they do not exist."""
    Base.metadata.create_all(engine)
