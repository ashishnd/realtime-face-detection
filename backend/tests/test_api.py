import io
import json
import uuid

import pytest
from PIL import Image

from app.db.session import get_session_factory
from app.repositories import roi_repository
from app.services.face_detector import FaceBox


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


def test_ws_preview_receives_processed_frame(client, session_id):
    jpeg = _tiny_jpeg()
    with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}/preview") as preview_ws:
        with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}/ingest") as ingest_ws:
            ingest_ws.send_bytes(jpeg)
            _ = ingest_ws.receive_text()
            out = preview_ws.receive_bytes()
            assert isinstance(out, (bytes, bytearray))
            assert len(out) > 16
            assert bytes(out).startswith(b"\xff\xd8")


def test_ws_ingest_rate_limit_error(client, session_id):
    vm = client.app.state.video_manager
    vm._settings.max_frames_per_minute = 1
    jpeg = _tiny_jpeg()

    with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}/ingest") as ws:
        ws.send_bytes(jpeg)
        first = json.loads(ws.receive_text())
        assert first["error"] in (None, "")

        ws.send_bytes(jpeg)
        second = json.loads(ws.receive_text())
        assert second["detected"] is False
        assert "rate limit" in second["error"].lower()


def test_ws_ingest_persists_roi_when_face_detected(client, session_id):
    class _StubDetector:
        def detect(self, rgb):
            return FaceBox(x_min=3.0, y_min=4.0, x_max=22.0, y_max=25.0, confidence=0.91)

    client.app.state.video_manager._detector = _StubDetector()

    with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}/ingest") as ws:
        ws.send_bytes(_tiny_jpeg())
        payload = json.loads(ws.receive_text())
        assert payload["detected"] is True
        assert payload["x_min"] == 3
        assert payload["y_min"] == 4
        assert payload["x_max"] == 22
        assert payload["y_max"] == 25

    r = client.get(f"/api/v1/sessions/{session_id}/roi")
    assert r.status_code == 200
    body = r.json()
    assert body["latest"] is not None
    assert body["latest"]["frame_number"] == payload["frame_number"]


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
