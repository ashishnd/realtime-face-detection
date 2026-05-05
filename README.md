# DevMesh Mega AI — Real-Time Face Detection Video Streaming

Containerized submission for the DevMesh Mega AI backend assessment.

## Tech stack

- Backend: `FastAPI`, `SQLAlchemy`, `Alembic`, `WebSockets`
- CV pipeline: `MediaPipe` (face detection), `Pillow` (ROI drawing), `NumPy`
- Frontend: `React` + `Vite`
- Database: `PostgreSQL`
- Orchestration: `Docker Compose`

OpenCV is not used.

## Architecture diagram

- Root image: `/Users/ashishdeshpande/mega-ai/architecture.png`
- Docs copy: `/Users/ashishdeshpande/mega-ai/docs/architecture.png`

## API surfaces

This implementation provides the 3 required functional endpoints:

1. Receive feed: `WS /api/v1/ws/sessions/{session_id}/ingest`
2. Serve processed feed: `WS /api/v1/ws/sessions/{session_id}/preview`
3. Serve ROI data: `GET /api/v1/sessions/{session_id}/roi`

Additional convenience routes:

- Create session: `POST /api/v1/sessions`
- MJPEG stream (optional viewer): `GET /api/v1/sessions/{session_id}/video.mjpeg`
- Health: `GET /healthz`
- Readiness: `GET /readyz`

ROI query params:

- `limit` (default 50, max 500)
- `before_frame` (optional; returns rows with smaller frame numbers)

## Data model

- `stream_sessions` — lifecycle for video sessions.
- `roi_detections` — per-frame ROI records.

See migration:

- `/Users/ashishdeshpande/mega-ai/backend/alembic/versions/20260504_0001_initial.py`

## Quick start (5-minute path)

### Prerequisites

- Docker + Docker Compose
- A webcam (for live frontend demo)

### Run

```bash
cd /Users/ashishdeshpande/mega-ai
docker compose up --build
```

### Open

- Frontend: `http://localhost:5173`
- Backend docs: `http://localhost:8000/docs`

### Demo flow

1. Click **Create session** in the frontend.
2. Click **Start camera + streams**.
3. The frontend sends JPEG frames over ingest WebSocket.
4. Backend detects face, draws axis-aligned ROI, stores ROI rows in Postgres.
5. Processed frames are shown via preview WebSocket.
6. ROI JSON is fetched from REST and rendered in the UI.

## Local development (without Docker)

### Backend

```bash
cd /Users/ashishdeshpande/mega-ai/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-cv.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd /Users/ashishdeshpande/mega-ai/frontend
npm install
npm run dev
```

## Configuration

Copy and adjust env values from:

- `/Users/ashishdeshpande/mega-ai/.env.example`

Key controls:

- `MAX_WS_MESSAGE_BYTES`
- `MAX_IMAGE_DIMENSION`
- `MAX_FRAMES_PER_MINUTE`
- `MAX_PREVIEW_SUBSCRIBERS`
- `CORS_ORIGINS`

## Error handling and no-face behavior

- Unknown session in WS: closes with code `4404`.
- Oversized frame or rate-limit breach: structured ingest ack with `error`.
- No detected face: `detected=false` in ingest ack; ROI insert is skipped.
- Unknown session for ROI route: `404`.

## Security fundamentals included

- Explicit CORS allowlist.
- Request/message limits to protect memory and abuse paths.
- Per-session frame rate limiting.
- SQLAlchemy parameterized interactions.
- Non-root backend container user.
- `.env` excluded via `.gitignore`.

## Testing

Backend tests are under:

- `/Users/ashishdeshpande/mega-ai/backend/tests`

Run:

```bash
cd /Users/ashishdeshpande/mega-ai/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## AI collaboration attestation

See:

- `/Users/ashishdeshpande/mega-ai/AI_ATTESTATION.md`

## Notes

- CV dependencies are separated:
  - `requirements.txt` (core app/test)
  - `requirements-cv.txt` (MediaPipe stack)
- If MediaPipe is unavailable at runtime, the detector returns no-face rather than crashing startup.

