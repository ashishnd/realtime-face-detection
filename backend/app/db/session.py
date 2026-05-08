from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

_engine = None
_SessionLocal = None


def reset_engine() -> None:
    """Test helper: clear cached engine after changing DATABASE_URL."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        engine_kwargs = {"pool_pre_ping": True}

        # FastAPI TestClient can touch the DB from multiple threads. For SQLite,
        # use one shared connection and disable same-thread enforcement so in-memory
        # test DB state (tables/data) is visible across request handling threads.
        if settings.database_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in settings.database_url:
                engine_kwargs["poolclass"] = StaticPool

        _engine = create_engine(settings.database_url, **engine_kwargs)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory():
    get_engine()
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
