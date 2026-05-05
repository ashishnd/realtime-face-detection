import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.config import get_settings  # noqa: E402
from app.db.session import get_db, get_engine, get_session_factory, reset_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    get_settings.cache_clear()
    reset_engine()
    engine = get_engine()
    Base.metadata.create_all(engine)
    SessionLocal = get_session_factory()

    def override_get_db():
        db: Session = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        class _StubDetector:
            def detect(self, rgb):
                return None

        c.app.state.video_manager._detector = _StubDetector()
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture()
def session_id(client: TestClient) -> uuid.UUID:
    res = client.post("/api/v1/sessions")
    assert res.status_code == 201
    return uuid.UUID(res.json()["id"])
