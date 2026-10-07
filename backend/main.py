from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from backend.live import (
    handle_live_session,
    get_gemini_api_key,
    get_gemini_live_model,
    ENV_PATH,
)

# Ensure project-root .env is loaded
load_dotenv(dotenv_path=ENV_PATH)

from backend.db import get_db_connection, DB_PATH
from backend.schema import (
    PathwaysRequest,
    PathwaysResultSchema,
    RecomputeRequest,
    RecomputeResultSchema,
)
from backend.engine import compute_pathways, recompute_pathways

app = FastAPI(title="SIH26097 Live Voice Assistant - Phase 2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    api_key = get_gemini_api_key()
    try:
        model = get_gemini_live_model()
    except ValueError:
        model = None

    db_ready = False
    try:
        if DB_PATH.exists():
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
            count = cur.fetchone()[0]
            conn.close()
            db_ready = count > 0
    except Exception:
        db_ready = False

    return {
        "status": "ok",
        "phase": 2,
        "model": model,
        "has_api_key": bool(api_key),
        "db_initialized": db_ready,
    }

@app.post("/api/pathways", response_model=PathwaysResultSchema)
def get_pathways_endpoint(payload: PathwaysRequest):
    return compute_pathways(
        profile=payload.profile,
        constraints=payload.constraints,
    )

@app.post("/api/recompute", response_model=RecomputeResultSchema)
def recompute_pathways_endpoint(payload: RecomputeRequest):
    return recompute_pathways(
        profile=payload.profile,
        previous_pathway_ids=payload.previous_pathway_ids,
        constraints=payload.constraints,
    )

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await websocket.accept()
    await handle_live_session(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
