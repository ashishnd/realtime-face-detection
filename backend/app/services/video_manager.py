from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.config import Settings
from app.repositories import roi_repository
from app.services.face_detector import FaceDetector
from app.services import frame_processor


@dataclass
class _SessionState:
    preview_subscribers: list[WebSocket] = field(default_factory=list)
    frame_seq: int = 0
    rate_times: deque[float] = field(default_factory=deque)
    latest_jpeg: bytes | None = None
    frame_event: asyncio.Event = field(default_factory=asyncio.Event)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class VideoManager:
    """In-memory session registry, preview fan-out, and rate limiting."""

    def __init__(self, settings: Settings, detector: FaceDetector) -> None:
        self._settings = settings
        self._detector = detector
        self._sessions: dict[uuid.UUID, _SessionState] = {}
        self._sessions_guard = asyncio.Lock()

    async def ensure_session(self, session_id: uuid.UUID) -> None:
        async with self._sessions_guard:
            if session_id not in self._sessions:
                self._sessions[session_id] = _SessionState()

    async def register_preview(self, session_id: uuid.UUID, ws: WebSocket) -> None:
        async with self._sessions_guard:
            st = self._sessions.get(session_id)
            if st is None:
                self._sessions[session_id] = _SessionState()
                st = self._sessions[session_id]
        async with st.lock:
            if len(st.preview_subscribers) >= self._settings.max_preview_subscribers:
                raise RuntimeError("Too many preview subscribers for this session")
            st.preview_subscribers.append(ws)

    async def unregister_preview(self, session_id: uuid.UUID, ws: WebSocket) -> None:
        async with self._sessions_guard:
            st = self._sessions.get(session_id)
        if st is None:
            return
        async with st.lock:
            if ws in st.preview_subscribers:
                st.preview_subscribers.remove(ws)

    async def wait_for_latest_frame(self, session_id: uuid.UUID, timeout_s: float = 1.0) -> bytes | None:
        async with self._sessions_guard:
            st = self._sessions.setdefault(session_id, _SessionState())
        if st.latest_jpeg is not None:
            return st.latest_jpeg
        try:
            await asyncio.wait_for(st.frame_event.wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            return None
        return st.latest_jpeg

    async def _allow_frame(self, st: _SessionState) -> bool:
        now = time.monotonic()
        window = 60.0
        async with st.lock:
            while st.rate_times and now - st.rate_times[0] > window:
                st.rate_times.popleft()
            limit = self._settings.max_frames_per_minute
            if len(st.rate_times) >= limit:
                return False
            st.rate_times.append(now)
            return True

    def _process_jpeg_cpu_only(self, jpeg_bytes: bytes, frame_number: int) -> dict:
        """Runs in a worker thread: decode, detect, draw. No database."""
        rgb, w, h = frame_processor.jpeg_to_rgb(jpeg_bytes)
        if w > self._settings.max_image_dimension or h > self._settings.max_image_dimension:
            raise ValueError("Image dimensions exceed configured maximum")

        box = self._detector.detect(rgb)
        if box is None:
            return {
                "frame_number": frame_number,
                "detected": False,
                "x_min": None,
                "y_min": None,
                "x_max": None,
                "y_max": None,
                "confidence": None,
                "annotated_jpeg": jpeg_bytes,
                "error": None,
            }

        x0, y0, x1, y1 = frame_processor.clamp_int_box(box.x_min, box.y_min, box.x_max, box.y_max, w, h)
        annotated, _ = frame_processor.annotate_jpeg_with_box(jpeg_bytes, box)

        return {
            "frame_number": frame_number,
            "detected": True,
            "x_min": x0,
            "y_min": y0,
            "x_max": x1,
            "y_max": y1,
            "confidence": box.confidence,
            "annotated_jpeg": annotated,
            "frame_width": w,
            "frame_height": h,
            "error": None,
        }

    async def handle_ingest_frame(
        self,
        db: Session,
        session_id: uuid.UUID,
        jpeg_bytes: bytes,
    ) -> dict:
        async with self._sessions_guard:
            st = self._sessions.setdefault(session_id, _SessionState())

        if len(jpeg_bytes) > self._settings.max_ws_message_bytes:
            raise ValueError("Frame exceeds maximum message size")

        if not await self._allow_frame(st):
            raise ValueError("Frame rate limit exceeded for this session")

        async with st.lock:
            st.frame_seq += 1
            frame_number = st.frame_seq

        loop = asyncio.get_running_loop()

        try:
            result = await loop.run_in_executor(None, lambda: self._process_jpeg_cpu_only(jpeg_bytes, frame_number))
        except Exception as exc:  # noqa: BLE001
            try:
                await self._broadcast_preview(session_id, jpeg_bytes)
            except Exception:
                pass
            return {
                "frame_number": frame_number,
                "detected": False,
                "x_min": None,
                "y_min": None,
                "x_max": None,
                "y_max": None,
                "confidence": None,
                "error": str(exc),
            }

        annotated_jpeg = result["annotated_jpeg"]
        frame_width = result.get("frame_width")
        frame_height = result.get("frame_height")

        if result.get("detected") and frame_width is not None and frame_height is not None:
            roi_repository.insert_roi(
                db,
                session_id=session_id,
                frame_number=int(result["frame_number"]),
                x_min=int(result["x_min"]),
                y_min=int(result["y_min"]),
                x_max=int(result["x_max"]),
                y_max=int(result["y_max"]),
                confidence=float(result["confidence"]) if result.get("confidence") is not None else None,
                frame_width=int(frame_width),
                frame_height=int(frame_height),
            )

        await self._broadcast_preview(session_id, annotated_jpeg)
        return {k: v for k, v in result.items() if k not in ("annotated_jpeg", "frame_width", "frame_height")}

    async def _broadcast_preview(self, session_id: uuid.UUID, jpeg_bytes: bytes) -> None:
        async with self._sessions_guard:
            st = self._sessions.get(session_id)
        if st is None:
            return
        async with st.lock:
            st.latest_jpeg = jpeg_bytes
            st.frame_event.set()
            st.frame_event = asyncio.Event()
            targets = list(st.preview_subscribers)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_bytes(jpeg_bytes)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.unregister_preview(session_id, ws)
