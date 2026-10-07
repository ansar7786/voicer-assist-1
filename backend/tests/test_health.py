import sqlite3
from fastapi.testclient import TestClient
from backend.main import app
from backend.db import DB_PATH, get_db_connection

client = TestClient(app)

def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["phase"] == 3
    assert data["db_initialized"] is True

def test_db_tables_exist():
    assert DB_PATH.exists()
    conn = get_db_connection()
    cursor = conn.cursor()
    tables = [
        row[0]
        for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    conn.close()

    expected_tables = [
        "nsqf_qualifications",
        "training_centres",
        "opportunities",
        "skill_adjacency",
        "sample_profiles",
        "sessions",
        "edit_log",
    ]
    for table in expected_tables:
        assert table in tables, f"Expected table '{table}' not found in database"
