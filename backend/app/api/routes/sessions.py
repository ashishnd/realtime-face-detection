import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import roi_repository
from app.schemas.session import SessionCreateResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session(db: Session = Depends(get_db)) -> SessionCreateResponse:
    row = roi_repository.create_session(db)
    return SessionCreateResponse.model_validate(row)


@router.get("/{session_id}", response_model=SessionCreateResponse)
def get_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> SessionCreateResponse:
    row = roi_repository.get_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return SessionCreateResponse.model_validate(row)
