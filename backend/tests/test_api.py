import io
import json
import uuid

import pytest
from PIL import Image

from app.db.session import get_session_factory
from app.repositories import roi_repository


def _tiny_jpeg() -> bytes:
    im = Image.new("RGB", (64, 48), color=(200, 200, 200))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_session(client):
    r = client.post("/api/v1/sessions")
    assert r.status_code == 201
    body = r.json()
    assert "id" in body
    assert body["status"] == "active"


def test_roi_unknown_session(client):
    rid = uuid.uuid4()
    r = client.get(f"/api/v1/sessions/{rid}/roi")
    assert r.status_code == 404


def test_roi_empty_history(client, session_id):
    r = client.get(f"/api/v1/sessions/{session_id}/roi")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["latest"] is None


def test_ws_ingest_smoke(client, session_id):
    jpeg = _tiny_jpeg()
    with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}/ingest") as ws:
        ws.send_bytes(jpeg)
        msg = ws.receive_text()
        payload = json.loads(msg)
        assert "frame_number" in payload
        assert "detected" in payload


def test_roi_before_frame_filter(client, session_id):
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        roi_repository.insert_roi(
            db,
            session_id=session_id,
            frame_number=10,
            x_min=1,
            y_min=2,
            x_max=30,
            y_max=40,
            confidence=0.8,
            frame_width=64,
            frame_height=48,
        )
        roi_repository.insert_roi(
            db,
            session_id=session_id,
            frame_number=20,
            x_min=2,
            y_min=3,
            x_max=31,
            y_max=41,
            confidence=0.85,
            frame_width=64,
            frame_height=48,
        )

    r = client.get(f"/api/v1/sessions/{session_id}/roi?before_frame=20&limit=10")
    assert r.status_code == 200
    body = r.json()
    assert [row["frame_number"] for row in body["items"]] == [10]
    assert body["latest"]["frame_number"] == 20
