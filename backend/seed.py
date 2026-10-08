import csv
from pathlib import Path
from backend.db import get_db_connection, init_db, DB_DIR

DATA_DIR = Path(__file__).resolve().parent / "data"

def seed_database():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Seed nsqf_qualifications
    nsqf_csv = DATA_DIR / "nsqf_qualifications.csv"
    if nsqf_csv.exists():
        cursor.execute("DROP TABLE IF EXISTS nsqf_qualifications")
        init_db()
        with open(nsqf_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute("""
                INSERT OR REPLACE INTO nsqf_qualifications (
                    id, trade, qualification_name, nsqf_level, entry_education,
                    duration_months, sector, self_employment_suitable, requires_travel,
                    equipment_needed, route_type, source_url, source_note, last_verified, is_sample,
                    delivery_mode, equipment_obtainable
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["id"], row["trade"], row["qualification_name"],
                    int(row["nsqf_level"]), row["entry_education"],
                    int(row["duration_months"]), row["sector"],
                    int(row["self_employment_suitable"]), int(row["requires_travel"]),
                    row.get("equipment_needed", ""), row["route_type"],
                    row.get("source_url", ""), row.get("source_note", ""),
                    row.get("last_verified", ""), int(row["is_sample"]),
                    row.get("delivery_mode", "either"), int(row.get("equipment_obtainable", 1))
                ))
        print(f"Seeded nsqf_qualifications from {nsqf_csv.name}")

    # 2. Seed training_centres
    tc_csv = DATA_DIR / "training_centres.csv"
    if tc_csv.exists():
        with open(tc_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute("""
                INSERT OR REPLACE INTO training_centres (
                    id, name, block, trade, seats, next_batch_date, mode, is_sample
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["id"], row["name"], row["block"], row["trade"],
                    int(row["seats"]), row.get("next_batch_date", ""),
                    row.get("mode", ""), int(row["is_sample"])
                ))
        print(f"Seeded training_centres from {tc_csv.name}")

    # 3. Seed opportunities
    opp_csv = DATA_DIR / "opportunities.csv"
    if opp_csv.exists():
        with open(opp_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute("""
                INSERT OR REPLACE INTO opportunities (
                    id, trade, type, block, source_note, verified, is_sample
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["id"], row["trade"], row["type"], row["block"],
                    row.get("source_note", ""), int(row["verified"]), int(row["is_sample"])
                ))
        print(f"Seeded opportunities from {opp_csv.name}")

    # 4. Seed skill_adjacency
    adj_csv = DATA_DIR / "skill_adjacency.csv"
    if adj_csv.exists():
        cursor.execute("DELETE FROM skill_adjacency")
        with open(adj_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute("""
                INSERT INTO skill_adjacency (from_skill, to_trade, closeness)
                VALUES (?, ?, ?)
                """, (row["from_skill"], row["to_trade"], row["closeness"]))
        print(f"Seeded skill_adjacency from {adj_csv.name}")

    conn.commit()
    conn.close()

    # 5. Seed sample_profiles (Phase 6)
    from backend.data.generate_sample_profiles import seed_sample_profiles
    seed_sample_profiles()

    print("Database seeding completed successfully.")

if __name__ == "__main__":
    seed_database()
