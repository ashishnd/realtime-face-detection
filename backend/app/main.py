from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import roi, sessions, video
from app.config import get_settings
from app.db.session import get_engine
from app.services.face_detector import FaceDetector
from app.services.video_manager import VideoManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    detector = FaceDetector()
    app.state.settings = settings
    app.state.face_detector = detector
    app.state.video_manager = VideoManager(settings, detector)
    yield
    detector.close()


app = FastAPI(title="Mega AI Face Stream", version="1.0.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api/v1")
app.include_router(roi.router, prefix="/api/v1")
app.include_router(video.router, prefix="/api/v1")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ready"}
