import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_DIR = PROJECT_ROOT / "backend" / "data"
DB_PATH = Path(os.getenv("SQLITE_DB_PATH", str(DB_DIR / "app.db")))

def get_db_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. nsqf_qualifications
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nsqf_qualifications (
        id TEXT PRIMARY KEY,
        trade TEXT NOT NULL,
        qualification_name TEXT NOT NULL,
        nsqf_level INTEGER NOT NULL,
        entry_education TEXT NOT NULL,
        duration_months INTEGER NOT NULL,
        sector TEXT NOT NULL,
        self_employment_suitable INTEGER NOT NULL,
        requires_travel INTEGER NOT NULL,
        equipment_needed TEXT,
        route_type TEXT NOT NULL,
        source_url TEXT,
        source_note TEXT,
        last_verified TEXT,
        is_sample INTEGER NOT NULL,
        delivery_mode TEXT NOT NULL DEFAULT 'either',
        equipment_obtainable INTEGER NOT NULL DEFAULT 1
    );
    """)

    # 2. training_centres
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS training_centres (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        block TEXT NOT NULL,
        trade TEXT NOT NULL,
        seats INTEGER NOT NULL,
        next_batch_date TEXT,
        mode TEXT,
        is_sample INTEGER NOT NULL
    );
    """)

    # 3. opportunities
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS opportunities (
        id TEXT PRIMARY KEY,
        trade TEXT NOT NULL,
        type TEXT NOT NULL,
        block TEXT NOT NULL,
        source_note TEXT,
        verified INTEGER NOT NULL,
        is_sample INTEGER NOT NULL
    );
    """)

    # 4. skill_adjacency
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS skill_adjacency (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_skill TEXT NOT NULL,
        to_trade TEXT NOT NULL,
        closeness TEXT NOT NULL
    );
    """)

    # 5. sample_profiles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sample_profiles (
        id TEXT PRIMARY KEY,
        block TEXT NOT NULL,
        interested_trade TEXT NOT NULL,
        education_level TEXT NOT NULL,
        skills TEXT,
        missing_skills TEXT,
        generated INTEGER NOT NULL
    );
    """)

    # 6. sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        language TEXT,
        transcript_json TEXT,
        profile_json TEXT,
        constraints_json TEXT,
        consent_official_view INTEGER NOT NULL
    );
    """)

    # 7. edit_log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS edit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        field TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        actor TEXT NOT NULL,
        ts TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
