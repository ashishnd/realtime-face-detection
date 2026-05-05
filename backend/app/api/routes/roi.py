import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import roi_repository
from app.schemas.roi import ROIDetectionRead, ROIListResponse

router = APIRouter(prefix="/sessions", tags=["roi"])


@router.get(
    "/{session_id}/roi",
    response_model=ROIListResponse,
    responses={
        200: {
            "description": "ROI rows in descending frame order plus latest ROI snapshot.",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": 42,
                                "session_id": "11111111-1111-1111-1111-111111111111",
                                "frame_number": 120,
                                "x_min": 110,
                                "y_min": 80,
                                "x_max": 280,
                                "y_max": 260,
                                "confidence": 0.94,
                                "frame_width": 640,
                                "frame_height": 480,
                                "created_at": "2026-05-05T08:30:00Z",
                            }
                        ],
                        "latest": {
                            "id": 42,
                            "session_id": "11111111-1111-1111-1111-111111111111",
                            "frame_number": 120,
                            "x_min": 110,
                            "y_min": 80,
                            "x_max": 280,
                            "y_max": 260,
                            "confidence": 0.94,
                            "frame_width": 640,
                            "frame_height": 480,
                            "created_at": "2026-05-05T08:30:00Z",
                        },
                    }
                }
            },
        },
        404: {"description": "Session not found"},
    },
)
def list_roi(
    session_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=500, description="Maximum rows to return."),
    before_frame: int | None = Query(
        None,
        ge=1,
        description="Return rows where frame_number is strictly less than this value.",
    ),
    db: Session = Depends(get_db),
) -> ROIListResponse:
    if roi_repository.get_session(db, session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    rows = roi_repository.list_roi_for_session(db, session_id, limit=limit, before_frame=before_frame)
    latest = roi_repository.latest_roi(db, session_id)
    return ROIListResponse(
        items=[ROIDetectionRead.model_validate(r) for r in rows],
        latest=ROIDetectionRead.model_validate(latest) if latest is not None else None,
    )
