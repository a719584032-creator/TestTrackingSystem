"""Legacy database helper using SQLAlchemy engine."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, Connection


class LegacyDatabase:
    """Light-weight SQLAlchemy engine wrapper for the legacy MySQL database."""

    def __init__(self) -> None:
        self._engine: Optional[Engine] = None

    def init_app(self, app) -> None:
        uri = app.config.get("LEGACY_DATABASE_URI")
        if not uri:
            app.logger.warning("LEGACY_DATABASE_URI is not configured; legacy data APIs are disabled.")
            return
        self._engine = create_engine(uri, pool_pre_ping=True)

    @contextmanager
    def connect(self) -> Generator[Connection, None, None]:
        if not self._engine:
            raise RuntimeError("Legacy database engine is not initialized")
        connection = self._engine.connect()
        try:
            yield connection
        finally:
            connection.close()

    def get_engine(self) -> Engine:
        if not self._engine:
            raise RuntimeError("Legacy database engine is not initialized")
        return self._engine


legacy_db = LegacyDatabase()

__all__ = ["legacy_db"]
