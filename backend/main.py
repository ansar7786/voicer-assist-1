from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from collections import Counter
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

app = FastAPI(title="SIH26097 Live Voice Assistant - Phase 6")

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
        "phase": 7,
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
# Official View Summary (Phase 6)
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/official/summary")
def get_official_summary(
    block: Optional[str] = None,
    trade: Optional[str] = None,
):
    """
    District Official View aggregated statistics computed purely via SQL (FR-64, FR-65).
    Features:
    - Pure SQL aggregations (never hardcoded numbers).
    - Small-cell suppression: groups under 5 merged into 'Other (suppressed)'.
    - Separate tracking of generated sample profiles vs consented real sessions.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Filter dropdown options
    cur.execute("SELECT DISTINCT block FROM sample_profiles ORDER BY block")
    all_blocks = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT DISTINCT interested_trade FROM sample_profiles ORDER BY interested_trade")
    all_trades = [r[0] for r in cur.fetchall()]

    # 2. Demand by Trade (with small-cell suppression for groups < 5)
    query_demand = """
        SELECT interested_trade, COUNT(*) as cnt
        FROM sample_profiles
        WHERE 1=1
    """
    params_demand = []
    if block:
        query_demand += " AND block = ?"
        params_demand.append(block)
    if trade:
        query_demand += " AND interested_trade = ?"
        params_demand.append(trade)
    query_demand += " GROUP BY interested_trade ORDER BY cnt DESC"

    cur.execute(query_demand, params_demand)
    rows_demand = cur.fetchall()

    demand_by_trade = []
    suppressed_count = 0
    for r in rows_demand:
        tr_name = r["interested_trade"]
        cnt = r["cnt"]
        if cnt < 5 and not trade:
            suppressed_count += cnt
        else:
            demand_by_trade.append({
                "trade": tr_name,
                "count": cnt,
                "is_suppressed": False,
            })

    if suppressed_count > 0:
        demand_by_trade.append({
            "trade": "Other (suppressed)",
            "count": suppressed_count,
            "is_suppressed": True,
        })

    # 3. Missing Skill Gaps across filtered population
    query_skills = "SELECT missing_skills FROM sample_profiles WHERE 1=1"
    params_skills = []
    if block:
        query_skills += " AND block = ?"
        params_skills.append(block)
    if trade:
        query_skills += " AND interested_trade = ?"
        params_skills.append(trade)

    cur.execute(query_skills, params_skills)
    skill_counter = Counter()
    for row in cur.fetchall():
        ms = row["missing_skills"]
        if ms:
            for s in ms.split(","):
                s_clean = s.strip()
                if s_clean:
                    skill_counter[s_clean] += 1

    top_skill_gaps = [
        {"skill": k.replace("_", " ").title(), "raw_skill": k, "count": v}
        for k, v in skill_counter.most_common(8)
    ]

    # 4. Capacity vs Demand
    query_tc = "SELECT block, trade, SUM(seats) as seats FROM training_centres WHERE 1=1"
    params_tc = []
    if block:
        query_tc += " AND block = ?"
        params_tc.append(block)
    if trade:
        query_tc += " AND trade = ?"
        params_tc.append(trade)
    query_tc += " GROUP BY block, trade"

    cur.execute(query_tc, params_tc)
    seats_map = {(r["block"], r["trade"]): r["seats"] for r in cur.fetchall()}

    query_bt = """
        SELECT block, interested_trade, COUNT(*) as cnt
        FROM sample_profiles
        WHERE 1=1
    """
    params_bt = []
    if block:
        query_bt += " AND block = ?"
        params_bt.append(block)
    if trade:
        query_bt += " AND interested_trade = ?"
        params_bt.append(trade)
    query_bt += " GROUP BY block, interested_trade ORDER BY block, cnt DESC"

    cur.execute(query_bt, params_bt)
    capacity_table = []
    for r in cur.fetchall():
        b = r["block"]
        t = r["interested_trade"]
        cnt = r["cnt"]
        seats = seats_map.get((b, t), 0)
        gap = cnt - seats
        capacity_table.append({
            "block": b,
            "trade": t,
            "interested_count": cnt,
            "seats": seats,
            "gap": gap,
            "is_shortfall": gap > 0,
            "is_suppressed": cnt < 5 and not trade,
        })

    # Total sample profiles count
    query_total = "SELECT COUNT(*) FROM sample_profiles WHERE 1=1"
    params_total = []
    if block:
        query_total += " AND block = ?"
        params_total.append(block)
    if trade:
        query_total += " AND interested_trade = ?"
        params_total.append(trade)
    cur.execute(query_total, params_total)
    total_profiles = cur.fetchone()[0]

    # 5. Consented Real Sessions (kept strictly separate & labelled differently)
    cur.execute("""
        SELECT id, created_at, language, profile_json
        FROM sessions
        WHERE consent_official_view = 1
        ORDER BY created_at DESC
    """)
    consented_rows = cur.fetchall()
    consented_sessions = []
    for cr in consented_rows:
        prof = {}
        try:
            if cr["profile_json"]:
                prof = json.loads(cr["profile_json"])
        except Exception:
            pass
        consented_sessions.append({
            "session_id_masked": f"{cr['id'][:8]}...",
            "created_at": cr["created_at"],
            "education": prof.get("education_level", "Not stated"),
            "interests": prof.get("interests", []),
            "skills": prof.get("skills", []),
            "language": cr["language"] or "en",
        })

    conn.close()

    return {
        "filter": {
            "block": block,
            "trade": trade,
        },
        "available_blocks": all_blocks,
        "available_trades": all_trades,
        "sample_data": {
            "total_profiles": total_profiles,
            "demand_by_trade": demand_by_trade,
            "skill_gaps": top_skill_gaps,
            "capacity": capacity_table,
        },
        "consented_sessions": {
            "total_consented": len(consented_sessions),
            "sessions": consented_sessions,
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/extract — Fallback Typed Input Extraction (Phase 7, FR-66)
# ──────────────────────────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    text: str
    current_profile: Optional[Dict[str, Any]] = None
    language: Optional[str] = "en"


class ExtractResponse(BaseModel):
    extracted: Dict[str, Any]
    profile: Dict[str, Any]
    message: str


@app.post("/api/extract", response_model=ExtractResponse)
def extract_endpoint(payload: ExtractRequest):
    import os
    import re
    from backend.blocklist import check_blocked
    from backend.normalize import (
        normalize_education,
        normalize_mobility,
        normalize_work_preference,
        normalize_trade,
        normalize_skill,
        normalize_asset,
    )

    raw_text = payload.text.strip()
    if not raw_text:
        return ExtractResponse(
            extracted={},
            profile=payload.current_profile or {},
            message="No text provided for extraction.",
        )

    # Privacy Blocklist Check
    is_blocked, blocked_reason = check_blocked("input_text", raw_text)
    if is_blocked:
        return ExtractResponse(
            extracted={},
            profile=payload.current_profile or {},
            message=f"Restricted {blocked_reason} content detected and excluded.",
        )

    extracted = {}
    profile = dict(payload.current_profile or {})

    # 1. Deterministic Normalizers across text
    from backend.normalize import EDUCATION_SYNONYMS, clean_input, _matches_pattern
    edu = normalize_education(raw_text)
    raw_clean = clean_input(raw_text)
    is_edu_mentioned = False
    if edu != "none":
        is_edu_mentioned = True
    else:
        for syn in EDUCATION_SYNONYMS.get("none", []):
            if _matches_pattern(syn, raw_clean):
                is_edu_mentioned = True
                break

    if is_edu_mentioned:
        extracted["education_level"] = edu
        profile["education_level"] = edu

    mob = normalize_mobility(raw_text)
    if mob:
        extracted["mobility"] = mob
        profile["mobility"] = mob

    wp = normalize_work_preference(raw_text)
    if wp:
        extracted["work_preference"] = wp
        profile["work_preference"] = wp

    tr = normalize_trade(raw_text)
    if tr:
        extracted["interests"] = [tr]
        existing_interests = profile.get("interests", [])
        if tr not in existing_interests:
            profile["interests"] = existing_interests + [tr]

    sk = normalize_skill(raw_text)
    if sk:
        extracted["skills"] = [sk]
        existing_skills = profile.get("skills", [])
        if sk not in existing_skills:
            profile["skills"] = existing_skills + [sk]

    ast = normalize_asset(raw_text)
    if ast:
        extracted["assets"] = [ast]
        existing_assets = profile.get("assets", [])
        if ast not in existing_assets:
            profile["assets"] = existing_assets + [ast]

    # Months regex (e.g., 3 months, 6 నెలలు, 2 महीने)
    m_match = re.search(r'(\d+)\s*(?:month|months|mo|నెలలు|నెలల|महीने|माह)', raw_text, re.IGNORECASE)
    if m_match:
        try:
            months = int(m_match.group(1))
            if 1 <= months <= 12:
                extracted["max_training_months"] = months
                profile["max_training_months"] = months
        except ValueError:
            pass

    # Optional: LLM Enhancement if GEMINI_TEXT_MODEL and API key present
    api_key = get_gemini_api_key()
    text_model = os.getenv("GEMINI_TEXT_MODEL", "").strip()
    if api_key and text_model and not extracted:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = (
                "Extract structured livelihood qualification fields from this user message into JSON. "
                "Allowed keys: education_level, skills (list), interests (list), mobility, max_training_months (int), work_preference. "
                "NO demographic, caste, religion, address, or ID fields. Return JSON only:\n"
                f"{raw_text}"
            )
            resp = client.models.generate_content(
                model=text_model,
                contents=prompt,
            )
            if resp and resp.text:
                clean_json_str = resp.text.strip().removeprefix("```json").removesuffix("```").strip()
                parsed = json.loads(clean_json_str)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if v:
                            extracted[k] = v
                            profile[k] = v
        except Exception:
            pass

    msg = f"Extracted {len(extracted)} field(s) successfully." if extracted else "Could not extract specific attributes from message."
    return ExtractResponse(
        extracted=extracted,
        profile=profile,
        message=msg,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/demo/replay/{persona} — Cached Demo Replays (Phase 7, FR-68)
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/demo/replay/{persona_id}")
def demo_replay_endpoint(persona_id: str):
    from backend.demo_replay import get_demo_replay
    try:
        return get_demo_replay(persona_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
