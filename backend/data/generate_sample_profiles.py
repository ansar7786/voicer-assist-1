"""
Generate realistic sample livelihood profiles for District Official View (Phase 6).
Deterministic generation with fixed random seed (seed=42).
STRICT PRIVACY: NO names, caste, community, religion, address, or ID fields.
"""
import random
import sqlite3
from pathlib import Path
from backend.db import get_db_connection, init_db

# Fixed random seed for reproducible demo data
RANDOM_SEED = 42

BLOCKS = ["Anandapuram", "Pendurthi", "Bheemunipatnam", "Padmanabham"]

TRADES_AND_SKILLS = {
    "tailoring": {
        "skills": ["hand_sewing", "cutting", "embroidery", "measurement", "alteration"],
        "missing": ["machine_operation", "pattern_making", "industrial_stitching", "garment_finishing"],
    },
    "catering": {
        "skills": ["home_cooking", "food_prep", "cleaning", "spice_mixing"],
        "missing": ["commercial_hygiene", "bulk_cooking", "menu_planning", "food_safety_regulations"],
    },
    "electrician": {
        "skills": ["basic_wiring", "bulb_fitting", "fuse_repair"],
        "missing": ["three_phase_wiring", "safety_earthing", "multimeter_diagnostics", "motor_rewinding"],
    },
    "solar_technician": {
        "skills": ["basic_electrical", "roof_work", "hand_tools"],
        "missing": ["pv_module_mounting", "inverter_synchronization", "solar_safety_standards", "battery_maintenance"],
    },
    "beauty_wellness": {
        "skills": ["threading", "hair_styling", "henna_application"],
        "missing": ["skin_treatment", "bridal_makeup", "chemical_safety", "salon_sanitization"],
    },
    "dairy_farming": {
        "skills": ["cattle_feeding", "milking", "shed_cleaning"],
        "missing": ["disease_identification", "artificial_insemination", "bulk_milk_cooling", "feed_ratio_calculation"],
    },
    "retail_sales": {
        "skills": ["customer_interaction", "counter_billing", "stock_arranging"],
        "missing": ["pos_software_operation", "inventory_reconciliation", "digital_payments_audit"],
    },
}

EDUCATION_DISTRIBUTION = ["primary", "8th", "8th", "10th", "10th", "10th", "12th", "graduate"]


def generate_profiles(count_total: int = 150) -> list[dict]:
    random.seed(RANDOM_SEED)
    profiles = []

    # 1. Anandapuram: High demand for tailoring (deliberate shortfall demo story)
    # 45 candidates wanting tailoring against 30 seats
    for i in range(45):
        trade = "tailoring"
        skills = random.sample(TRADES_AND_SKILLS[trade]["skills"], k=random.randint(1, 3))
        missing = random.sample(TRADES_AND_SKILLS[trade]["missing"], k=random.randint(1, 3))
        profiles.append({
            "block": "Anandapuram",
            "interested_trade": trade,
            "education_level": random.choice(EDUCATION_DISTRIBUTION),
            "skills": ",".join(skills),
            "missing_skills": ",".join(missing),
            "generated": 1,
        })

    # Anandapuram other trades (electrician, dairy)
    for _ in range(15):
        trade = random.choice(["electrician", "dairy_farming"])
        skills = random.sample(TRADES_AND_SKILLS[trade]["skills"], k=random.randint(1, 2))
        missing = random.sample(TRADES_AND_SKILLS[trade]["missing"], k=random.randint(1, 2))
        profiles.append({
            "block": "Anandapuram",
            "interested_trade": trade,
            "education_level": random.choice(EDUCATION_DISTRIBUTION),
            "skills": ",".join(skills),
            "missing_skills": ",".join(missing),
            "generated": 1,
        })

    # 2. Pendurthi: Tailoring (28 vs 25 seats -> mild shortfall) and solar technician
    for _ in range(28):
        trade = "tailoring"
        skills = random.sample(TRADES_AND_SKILLS[trade]["skills"], k=random.randint(1, 3))
        missing = random.sample(TRADES_AND_SKILLS[trade]["missing"], k=random.randint(1, 3))
        profiles.append({
            "block": "Pendurthi",
            "interested_trade": trade,
            "education_level": random.choice(EDUCATION_DISTRIBUTION),
            "skills": ",".join(skills),
            "missing_skills": ",".join(missing),
            "generated": 1,
        })

    for _ in range(18):
        trade = "solar_technician"
        skills = random.sample(TRADES_AND_SKILLS[trade]["skills"], k=random.randint(1, 2))
        missing = random.sample(TRADES_AND_SKILLS[trade]["missing"], k=random.randint(1, 2))
        profiles.append({
            "block": "Pendurthi",
            "interested_trade": trade,
            "education_level": random.choice(EDUCATION_DISTRIBUTION),
            "skills": ",".join(skills),
            "missing_skills": ",".join(missing),
            "generated": 1,
        })

    # 3. Bheemunipatnam: catering (22 vs 20 seats) & beauty_wellness (20 vs 25 seats)
    for _ in range(22):
        trade = "catering"
        skills = random.sample(TRADES_AND_SKILLS[trade]["skills"], k=random.randint(1, 2))
        missing = random.sample(TRADES_AND_SKILLS[trade]["missing"], k=random.randint(1, 2))
        profiles.append({
            "block": "Bheemunipatnam",
            "interested_trade": trade,
            "education_level": random.choice(EDUCATION_DISTRIBUTION),
            "skills": ",".join(skills),
            "missing_skills": ",".join(missing),
            "generated": 1,
        })

    for _ in range(20):
        trade = "beauty_wellness"
        skills = random.sample(TRADES_AND_SKILLS[trade]["skills"], k=random.randint(1, 2))
        missing = random.sample(TRADES_AND_SKILLS[trade]["missing"], k=random.randint(1, 2))
        profiles.append({
            "block": "Bheemunipatnam",
            "interested_trade": trade,
            "education_level": random.choice(EDUCATION_DISTRIBUTION),
            "skills": ",".join(skills),
            "missing_skills": ",".join(missing),
            "generated": 1,
        })

    # 4. Padmanabham: Low counts to specifically test small-cell suppression (< 5 per group)
    # 2 retail_sales and 2 dairy_farming
    for trade in ["retail_sales", "retail_sales", "dairy_farming", "dairy_farming"]:
        skills = random.sample(TRADES_AND_SKILLS[trade]["skills"], k=1)
        missing = random.sample(TRADES_AND_SKILLS[trade]["missing"], k=1)
        profiles.append({
            "block": "Padmanabham",
            "interested_trade": trade,
            "education_level": "10th",
            "skills": ",".join(skills),
            "missing_skills": ",".join(missing),
            "generated": 1,
        })

    # Assign IDs
    for idx, p in enumerate(profiles, 1):
        p["id"] = f"SP_{idx:04d}"

    return profiles


def seed_sample_profiles():
    init_db()
    profiles = generate_profiles()
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM sample_profiles WHERE generated = 1")

    for p in profiles:
        cur.execute("""
        INSERT INTO sample_profiles (id, block, interested_trade, education_level, skills, missing_skills, generated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            p["id"], p["block"], p["interested_trade"], p["education_level"],
            p["skills"], p["missing_skills"], p["generated"]
        ))

    conn.commit()
    conn.close()
    print(f"Successfully generated and seeded {len(profiles)} sample profiles (seed={RANDOM_SEED}).")


if __name__ == "__main__":
    seed_sample_profiles()
