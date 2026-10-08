"""
Tests for Phase 7: Fallbacks, Polish, Cached Replays, and Privacy Audit (PRD Section 11).
"""
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.db import get_db_connection
from backend.schema import ProfileSchema, ConstraintSchema

client = TestClient(app)


# ── 1. Typed Extraction Fallback Tests (FR-66) ───────────────────────────────

def test_extract_endpoint_valid():
    """POST /api/extract normalizes livelihood attributes from typed text."""
    payload = {
        "text": "నేను 10వ తరగతి చదివాను, నాకు కుట్టుపని వచ్చు. 3 నెలలు చేయగలను.",
        "current_profile": {},
        "language": "te",
    }
    resp = client.post("/api/extract", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    extracted = data["extracted"]
    profile = data["profile"]

    assert extracted.get("education_level") == "10th"
    assert "tailoring" in extracted.get("interests", []) or "tailoring" in extracted.get("skills", [])
    assert extracted.get("max_training_months") == 3
    assert profile.get("education_level") == "10th"


def test_extract_endpoint_blocklist():
    """POST /api/extract blocks caste/religion/address input."""
    payload = {
        "text": "I belong to Brahmin caste and live at 123 Main Street.",
        "current_profile": {},
    }
    resp = client.post("/api/extract", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "restricted" in data["message"].lower() or "excluded" in data["message"].lower()
    assert data["extracted"] == {}


def test_extract_endpoint_merges_profile():
    """POST /api/extract merges new attributes into existing profile."""
    payload = {
        "text": "I prefer self employment with home only mobility",
        "current_profile": {"education_level": "10th", "skills": ["tailoring"]},
    }
    resp = client.post("/api/extract", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    profile = data["profile"]

    assert profile.get("education_level") == "10th"
    assert "tailoring" in profile.get("skills", [])
    assert profile.get("mobility") == "home_only"
    assert profile.get("work_preference") == "self"


# ── 2. Cached Demo Replays Tests (FR-68) ─────────────────────────────────────

def test_demo_replay_persona_a():
    """GET /api/demo/replay/persona_a returns structured scripted replay for tailoring."""
    resp = client.get("/api/demo/replay/persona_a")
    assert resp.status_code == 200
    data = resp.json()

    assert data["persona_id"] == "persona_a"
    assert len(data["turns"]) == 3
    # Check turns structure
    for t in data["turns"]:
        assert "user_text" in t
        assert "assistant_text" in t
        assert "tool_call" in t
        assert "profile_snapshot" in t

    # Final turn must contain matched pathways
    last_turn = data["turns"][-1]
    assert last_turn["confirmed"] is True
    assert len(last_turn["pathways"]) > 0
    # Top pathway must be tailoring
    assert last_turn["pathways"][0]["trade"] == "tailoring"


def test_demo_replay_persona_b():
    """GET /api/demo/replay/persona_b returns structured scripted replay for catering."""
    resp = client.get("/api/demo/replay/persona_b")
    assert resp.status_code == 200
    data = resp.json()

    assert data["persona_id"] == "persona_b"
    assert len(data["turns"]) == 3
    last_turn = data["turns"][-1]
    assert last_turn["confirmed"] is True
    assert len(last_turn["pathways"]) > 0
    assert last_turn["pathways"][0]["trade"] == "catering"


def test_demo_replay_invalid():
    """GET /api/demo/replay/invalid returns 404."""
    resp = client.get("/api/demo/replay/non_existent_persona")
    assert resp.status_code == 404


# ── 3. Privacy Audit Tests (PRD Section 11.2) ────────────────────────────────

def test_privacy_audit_no_audio_files_stored():
    """Verify no raw audio files (.wav, .mp3, .pcm, .m4a) are stored in the repo."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    audio_extensions = {".wav", ".mp3", ".pcm", ".m4a", ".ogg", ".flac"}

    found_audio = []
    for p in repo_root.rglob("*"):
        # Ignore virtual env and git dirs
        if ".venv" in p.parts or ".git" in p.parts or "node_modules" in p.parts:
            continue
        if p.suffix.lower() in audio_extensions:
            found_audio.append(str(p))

    assert len(found_audio) == 0, f"Found audio files stored on disk: {found_audio}"


def test_privacy_audit_no_forbidden_fields_in_db():
    """Verify all database tables have zero demographic/forbidden columns."""
    forbidden = {"caste", "community", "religion", "address", "phone", "aadhaar", "id_number", "demographic"}
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    for tbl in tables:
        cur.execute(f"PRAGMA table_info({tbl})")
        columns = {col[1].lower() for col in cur.fetchall()}
        intersection = columns & forbidden
        assert len(intersection) == 0, f"Table '{tbl}' has forbidden identity columns: {intersection}"
    conn.close()


def test_privacy_audit_no_forbidden_fields_in_schemas():
    """Verify ProfileSchema and ConstraintSchema define no demographic fields."""
    forbidden = {"caste", "community", "religion", "address", "phone", "aadhaar", "id_number"}
    profile_fields = set(ProfileSchema.model_fields.keys())
    constraint_fields = set(ConstraintSchema.model_fields.keys())

    assert len(profile_fields & forbidden) == 0
    assert len(constraint_fields & forbidden) == 0
