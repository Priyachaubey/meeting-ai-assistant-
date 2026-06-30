from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# pool_size/max_overflow are QueuePool-only arguments (SQLAlchemy's own docs say so
# explicitly) — SQLite does NOT use QueuePool by default, so passing them for a sqlite://
# URL raises TypeError("Invalid argument(s) ... sent to create_engine()"). That happens
# right here, at this module's import time (engine = create_engine(...) below is a
# top-level statement) — which crashes the whole app before uvicorn ever binds to a port.
# This matters because core/config.py's DATABASE_URL *defaults* to a sqlite:// URL, so
# running this fresh without first pointing DATABASE_URL at a real Postgres instance hits
# this immediately. check_same_thread=False is the other half of real SQLite support:
# FastAPI runs sync dependencies (get_db is one) in a thread pool by default, and SQLite's
# default check_same_thread=True raises if a connection is used from a different thread
# than the one that created it — a real bug, just one that shows up per-request rather
# than at startup, so it wouldn't explain "uvicorn shuts down immediately" but would break
# every single request once the server *did* start.
_is_sqlite = settings.database_url.startswith("sqlite")
_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_engine(settings.database_url, **_engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a request-scoped Session, always closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
