import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.roi import ROIDetection
from app.models.session import StreamSession


def create_session(db: Session, session_id: uuid.UUID | None = None) -> StreamSession:
    now = datetime.now(timezone.utc)
    row = StreamSession(id=session_id or uuid.uuid4(), created_at=now, status="active")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_session(db: Session, session_id: uuid.UUID) -> StreamSession | None:
    return db.get(StreamSession, session_id)


def insert_roi(
    db: Session,
    *,
    session_id: uuid.UUID,
    frame_number: int,
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
    confidence: float | None,
    frame_width: int,
    frame_height: int,
) -> ROIDetection:
    now = datetime.now(timezone.utc)
    row = ROIDetection(
        session_id=session_id,
        frame_number=frame_number,
        x_min=x_min,
        y_min=y_min,
        x_max=x_max,
        y_max=y_max,
        confidence=confidence,
        frame_width=frame_width,
        frame_height=frame_height,
        created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_roi_for_session(
    db: Session,
    session_id: uuid.UUID,
    *,
    limit: int = 50,
    before_frame: int | None = None,
) -> list[ROIDetection]:
    stmt = select(ROIDetection).where(ROIDetection.session_id == session_id)
    if before_frame is not None:
        stmt = stmt.where(ROIDetection.frame_number < before_frame)
    stmt = stmt.order_by(ROIDetection.frame_number.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def latest_roi(db: Session, session_id: uuid.UUID) -> ROIDetection | None:
    stmt = (
        select(ROIDetection)
        .where(ROIDetection.session_id == session_id)
        .order_by(ROIDetection.frame_number.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()
