from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
import json

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
from backend.session_store import get_session

app = FastAPI(title="SIH26097 Live Voice Assistant - Phase 5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────────────────────

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
        "phase": 5,
        "model": model,
        "has_api_key": bool(api_key),
        "db_initialized": db_ready,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Engine endpoints
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# PATCH /api/session/{id}/profile — manual field editing
# ──────────────────────────────────────────────────────────────────────────────

class ProfilePatchRequest(BaseModel):
    field: str
    value: Any
    actor: str = "manual"   # "manual" | "admin"


@app.patch("/api/session/{session_id}/profile")
def patch_session_profile(session_id: str, payload: ProfilePatchRequest):
    """
    Manual field edit (e.g. from the ProfileCard UI).
    Writes to the in-memory session (if still active) AND persists to edit_log.
    Every change records old value, new value, and actor.
    Transcripts are NEVER touched here.
    """
    session = get_session(session_id)

    # Attempt to write to the in-memory session if it's alive
    old_value = None
    if session:
        old_value = session.profile.get(payload.field)
        session.update_field(
            payload.field,
            payload.value,
            source=payload.actor,
            confidence="stated",
        )

    # Always persist the edit_log row to the DB
    now_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Ensure session row exists (for sessions already closed)
        cur.execute(
            """
            INSERT OR IGNORE INTO sessions
                (id, created_at, language, transcript_json, profile_json,
                 constraints_json, consent_official_view)
            VALUES (?, ?, 'en', NULL, '{}', '{}', 0)
            """,
            (session_id, now_ts),
        )

        cur.execute(
            """
            INSERT INTO edit_log (session_id, field, old_value, new_value, actor, ts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                payload.field,
                json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
                json.dumps(payload.value, ensure_ascii=False),
                payload.actor,
                now_ts,
            ),
        )

        # If in-memory session exists, also update profile_json in DB
        if session:
            cur.execute(
                "UPDATE sessions SET profile_json = ? WHERE id = ?",
                (session.to_profile_json(), session_id),
            )

        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return {
        "ok": True,
        "session_id": session_id,
        "field": payload.field,
        "old_value": old_value,
        "new_value": payload.value,
        "actor": payload.actor,
        "ts": now_ts,
    }


@app.get("/api/session/{session_id}/profile")
def get_session_profile(session_id: str):
    """Return current in-memory profile for the given session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    profile_export = {k: v for k, v in session.profile.items() if not k.startswith("_")}
    return {
        "session_id": session_id,
        "profile": profile_export,
        "confidence": session.profile.get("_confidence", {}),
        "confirmed": session.confirmed,
    }


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/explain — rephrase engine reasons
# ──────────────────────────────────────────────────────────────────────────────

class ExplainRequest(BaseModel):
    reasons: Optional[list[str]] = None
    factors: Optional[list[dict]] = None
    pathway_name: Optional[str] = None
    user_profile: Optional[dict] = None
    language: Optional[str] = "en"


class ExplainResponse(BaseModel):
    explanation: str


@app.post("/api/explain", response_model=ExplainResponse)
def explain_endpoint(payload: ExplainRequest):
    reasons = []
    if payload.reasons:
        reasons.extend([r.strip() for r in payload.reasons if r and r.strip()])
    if payload.factors:
        for f in payload.factors:
            r = f.get("reason")
            if r and r.strip():
                reasons.append(r.strip())

    fallback = "; ".join(reasons) if reasons else "Meets your criteria and preferences"
    if not reasons:
        return ExplainResponse(explanation=fallback)

    import os
    api_key = get_gemini_api_key()
    text_model = os.getenv("GEMINI_TEXT_MODEL", "").strip()

    if not api_key or not text_model:
        return ExplainResponse(explanation=fallback)

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = (
            f"You are a helpful PM-AJAY career guidance assistant. "
            f"Rephrase the following factual qualification matching reasons into one friendly, clear spoken sentence in {payload.language}. "
            f"Do not invent new courses, facts, or placement guarantees. Use only these reasons: {'; '.join(reasons)}"
        )
        resp = client.models.generate_content(
            model=text_model,
            contents=prompt,
        )
        if resp and resp.text:
            return ExplainResponse(explanation=resp.text.strip())
    except Exception:
        pass

    return ExplainResponse(explanation=fallback)


# ──────────────────────────────────────────────────────────────────────────────
# WebSocket
# ──────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await websocket.accept()
    await handle_live_session(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
