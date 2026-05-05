import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.repositories import roi_repository
from app.schemas.roi import IngestAckMessage
from app.services.video_manager import VideoManager

router = APIRouter(tags=["video"])


def _session_exists(session_id: uuid.UUID) -> bool:
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        return roi_repository.get_session(db, session_id) is not None


@router.websocket("/ws/sessions/{session_id}/ingest")
async def ws_ingest(session_id: uuid.UUID, websocket: WebSocket) -> None:
    await websocket.accept()
    if not _session_exists(session_id):
        await websocket.close(code=4404, reason="Unknown session")
        return

    SessionLocal = get_session_factory()
    vm: VideoManager = websocket.app.state.video_manager
    await vm.ensure_session(session_id)

    db = SessionLocal()
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data is None:
                await websocket.send_text(
                    IngestAckMessage(
                        frame_number=-1,
                        detected=False,
                        error="Expected binary JPEG frame",
                    ).model_dump_json()
                )
                continue

            try:
                ack = await vm.handle_ingest_frame(db, session_id, data)
            except ValueError as exc:
                await websocket.send_text(
                    IngestAckMessage(
                        frame_number=-1,
                        detected=False,
                        error=str(exc),
                    ).model_dump_json()
                )
                continue

            await websocket.send_text(
                IngestAckMessage(
                    frame_number=int(ack["frame_number"]),
                    detected=bool(ack["detected"]),
                    x_min=ack.get("x_min"),
                    y_min=ack.get("y_min"),
                    x_max=ack.get("x_max"),
                    y_max=ack.get("y_max"),
                    confidence=ack.get("confidence"),
                    error=ack.get("error"),
                ).model_dump_json()
            )
    except WebSocketDisconnect:
        pass
    finally:
        db.close()


@router.websocket("/ws/sessions/{session_id}/preview")
async def ws_preview(session_id: uuid.UUID, websocket: WebSocket) -> None:
    await websocket.accept()
    if not _session_exists(session_id):
        await websocket.close(code=4404, reason="Unknown session")
        return

    vm: VideoManager = websocket.app.state.video_manager
    await vm.ensure_session(session_id)
    try:
        await vm.register_preview(session_id, websocket)
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        await vm.unregister_preview(session_id, websocket)


@router.get("/sessions/{session_id}/video.mjpeg")
async def mjpeg_stream(session_id: uuid.UUID, request: Request) -> StreamingResponse:
    if not _session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    async def generate():
        vm: VideoManager = request.app.state.video_manager
        boundary = b"--frame"
        while True:
            if await request.is_disconnected():
                break
            frame = await vm.wait_for_latest_frame(session_id, timeout_s=1.0)
            if frame is None:
                await asyncio.sleep(0.05)
                continue
            headers = b"Content-Type: image/jpeg\r\n" + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
            yield boundary + b"\r\n" + headers + frame + b"\r\n"

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"},
    )
