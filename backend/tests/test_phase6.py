"""
Tests for Phase 6: District Official View (FR-64, FR-65, Section 10).
"""
import json
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.db import get_db_connection

client = TestClient(app)


def test_official_summary_success():
    """GET /api/official/summary returns aggregated statistics from SQL."""
    resp = client.get("/api/official/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert "filter" in data
    assert "available_blocks" in data
    assert "available_trades" in data
    assert "sample_data" in data
    assert "consented_sessions" in data

    sample_data = data["sample_data"]
    assert sample_data["total_profiles"] > 0
    assert len(sample_data["demand_by_trade"]) > 0
    assert len(sample_data["skill_gaps"]) > 0
    assert len(sample_data["capacity"]) > 0


def test_sql_accuracy_matches_db():
    """Verify official summary counts match direct SQL queries against the DB."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sample_profiles")
    db_total = cur.fetchone()[0]
    conn.close()

    resp = client.get("/api/official/summary")
    data = resp.json()
    assert data["sample_data"]["total_profiles"] == db_total


def test_filter_by_block():
    """Filtering by block returns only records for that block."""
    resp = client.get("/api/official/summary?block=Anandapuram")
    assert resp.status_code == 200
    data = resp.json()

    assert data["filter"]["block"] == "Anandapuram"
    # All capacity rows must belong to Anandapuram
    for row in data["sample_data"]["capacity"]:
        assert row["block"] == "Anandapuram"


def test_filter_by_trade():
    """Filtering by trade returns only records for that trade."""
    resp = client.get("/api/official/summary?trade=tailoring")
    assert resp.status_code == 200
    data = resp.json()

    assert data["filter"]["trade"] == "tailoring"
    for row in data["sample_data"]["demand_by_trade"]:
        assert row["trade"] == "tailoring"


def test_small_cell_suppression():
    """Groups under 5 merge into 'Other (suppressed)'."""
    resp = client.get("/api/official/summary?block=Padmanabham")
    assert resp.status_code == 200
    data = resp.json()

    demand = data["sample_data"]["demand_by_trade"]
    # Padmanabham has 2 retail_sales and 2 dairy_farming profiles (each < 5)
    # They should be merged into "Other (suppressed)"
    suppressed_entries = [d for d in demand if d.get("is_suppressed")]
    assert len(suppressed_entries) > 0
    assert suppressed_entries[0]["trade"] == "Other (suppressed)"
    assert suppressed_entries[0]["count"] < 5 or suppressed_entries[0]["count"] == 4


def test_consented_sessions_separate_from_sample():
    """Consented real sessions are kept separate and labelled differently."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO sessions
            (id, created_at, language, transcript_json, profile_json, constraints_json, consent_official_view)
        VALUES
            ('test_official_sess_1', '2026-10-08T12:00:00Z', 'te', NULL,
             '{"education_level":"10th","interests":["tailoring"],"skills":["cutting"]}',
             '{}', 1)
    """)
    conn.commit()
    conn.close()

    resp = client.get("/api/official/summary")
    assert resp.status_code == 200
    data = resp.json()

    consented = data["consented_sessions"]
    assert consented["total_consented"] >= 1
    found = any(s["session_id_masked"].startswith("test_off") for s in consented["sessions"])
    assert found, "Consented session must appear in consented_sessions list"


def test_privacy_no_forbidden_fields():
    """Ensure sample_profiles table contains NO demographic or forbidden identity columns."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(sample_profiles)")
    columns = [row[1] for row in cur.fetchall()]
    conn.close()

    forbidden = ["name", "caste", "community", "religion", "address", "phone", "aadhaar", "id_number"]
    for f in forbidden:
        assert f not in columns, f"Forbidden column '{f}' found in sample_profiles table!"
