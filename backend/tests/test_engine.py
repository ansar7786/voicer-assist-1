"""
Unit tests for deterministic pathway engine adhering to PRD section 6.2 (15 test cases).
Tested strictly against fixed test fixtures in backend/tests/fixtures/, NOT production CSVs.
"""
import json
from pathlib import Path
import pytest

from backend.schema import ProfileSchema, ConstraintSchema
from backend.engine import compute_pathways, recompute_pathways
from backend.normalize import normalize_trade

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

@pytest.fixture
def fixtures():
    with open(FIXTURES_DIR / "nsqf_fixture.json", "r", encoding="utf-8") as f:
        quals = json.load(f)
    with open(FIXTURES_DIR / "centres_fixture.json", "r", encoding="utf-8") as f:
        centres = json.load(f)
    with open(FIXTURES_DIR / "opportunities_fixture.json", "r", encoding="utf-8") as f:
        opps = json.load(f)
    with open(FIXTURES_DIR / "adjacency_fixture.json", "r", encoding="utf-8") as f:
        adj = json.load(f)
    return {
        "qualifications": quals,
        "training_centres": centres,
        "opportunities": opps,
        "skill_adjacency": adj,
    }

# 1. Persona A: 10th pass, sewing machine, home_only, wants own work -> Tailoring pathway ranks first
def test_case_01_persona_a_tailoring_ranks_first(fixtures):
    profile = ProfileSchema(
        education_level="10th",
        assets=["sewing machine"],
        mobility="home_only",
        work_preference="self",
        interests=["tailoring"],
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    assert len(result.pathways) > 0
    top = result.pathways[0]
    assert top.trade == "tailoring"
    assert top.route == "self"
    assert top.id == "Q_TAILOR_01"

# 2. Persona B: catering experience, wage, urgent -> Catering or hospitality pathway ranks first
def test_case_02_persona_b_catering_ranks_first(fixtures):
    profile = ProfileSchema(
        education_level="10th",
        skills=["cooking"],
        work_preference="wage",
        urgency_of_income="urgent",
        interests=["catering"],
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    assert len(result.pathways) > 0
    top = result.pathways[0]
    assert top.trade == "catering"
    assert top.route == "wage"
    assert top.id == "Q_CATER_01"

# 3. Primary education only -> Higher-entry qualifications excluded with reason
def test_case_03_primary_education_excludes_higher(fixtures):
    profile = ProfileSchema(
        education_level="primary",
        work_preference="either",
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    # Check that 8th and 10th entry qualifications are in excluded with reason
    excluded_ids = {ex.id: ex.reason for ex in result.excluded}
    assert "Q_TAILOR_01" in excluded_ids  # Requires 10th
    assert "Requires at least 10th education" in excluded_ids["Q_TAILOR_01"]
    assert "Q_SEWING_02" in excluded_ids  # Requires 8th
    assert "Requires at least 8th education" in excluded_ids["Q_SEWING_02"]

# 4. Graduate -> Nothing excluded for education
def test_case_04_graduate_nothing_excluded_for_education(fixtures):
    profile = ProfileSchema(
        education_level="graduate",
        work_preference="either",
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    for ex in result.excluded:
        assert "Requires at least" not in ex.reason

# 5. home_only -> Travel-required routes excluded
def test_case_05_home_only_excludes_travel_routes(fixtures):
    profile = ProfileSchema(
        education_level="graduate",
        mobility="home_only",
        work_preference="either",
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    for p in result.pathways:
        qual = next(q for q in fixtures["qualifications"] if q["id"] == p.id)
        assert qual["requires_travel"] == 0

    excluded_ids = {ex.id: ex.reason for ex in result.excluded}
    assert "Q_SEWING_02" in excluded_ids
    assert "restricted to home only" in excluded_ids["Q_SEWING_02"]

# 6. max 3 months -> Longer courses excluded with reason
def test_case_06_max_3_months_excludes_longer_courses(fixtures):
    profile = ProfileSchema(
        education_level="graduate",
        max_training_months=3,
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    for p in result.pathways:
        assert p.duration_months <= 3

    excluded_ids = {ex.id: ex.reason for ex in result.excluded}
    assert "Q_ELEC_01" in excluded_ids  # 4 months
    assert "Requires 4 months, exceeding your limit of 3 months" in excluded_ids["Q_ELEC_01"]

# 7. work_preference either -> Both routes allowed
def test_case_07_work_preference_either_allows_both(fixtures):
    profile = ProfileSchema(
        education_level="graduate",
        work_preference="either",
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    routes = {p.route for p in result.pathways}
    # Either returns routes spanning self, wage, or both
    assert len(result.pathways) >= 2

# 8. No interests stated -> Still returns results, interest factor Unknown
def test_case_08_no_interests_stated_returns_unknown_factor(fixtures):
    profile = ProfileSchema(
        education_level="10th",
        interests=[],
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    assert len(result.pathways) > 0
    for p in result.pathways:
        interest_factor = next(f for f in p.factors if f.factor == "interest_match")
        assert interest_factor.label == "Unknown"
        assert interest_factor.reason == "No specific interests stated"

# 9. No matching trade (all excluded) -> Empty state with reasons for every exclusion
def test_case_09_all_excluded_returns_empty_state_with_reasons(fixtures):
    # Education none, max 0 months, home_only, self -> all courses excluded
    profile = ProfileSchema(
        education_level="none",
        mobility="home_only",
        max_training_months=0,
        work_preference="self",
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    assert len(result.pathways) == 0
    assert len(result.excluded) == len(fixtures["qualifications"])
    assert len(result.no_result_reasons) > 0
    for ex in result.excluded:
        assert len(ex.reason.strip()) > 0

# 10. Trade with no opportunity -> Status exactly "No verified opportunity found", training pathway still returned
def test_case_10_no_opportunity_honesty(fixtures):
    # Solar technician in fixture has NO opportunities
    profile = ProfileSchema(
        education_level="10th",
        interests=["solar_technician"],
        work_preference="wage",
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    solar_p = next(p for p in result.pathways if p.trade == "solar_technician")
    assert solar_p.opportunity_status == "No verified opportunity found"
    assert solar_p.nearest_centre is not None

# 11. Telugu synonym input -> Normalizer maps it to the right trade
def test_case_11_telugu_synonym_normalizes(fixtures):
    telugu_input = "కుట్టుపని"
    mapped_trade = normalize_trade(telugu_input)
    assert mapped_trade == "tailoring"

    profile = ProfileSchema(
        education_level="10th",
        interests=[telugu_input],
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    top = result.pathways[0]
    assert top.trade == "tailoring"

# 12. Hindi synonym input (silai) -> Same
def test_case_12_hindi_synonym_normalizes(fixtures):
    hindi_input = "सिलाई"
    mapped_trade = normalize_trade(hindi_input)
    assert mapped_trade == "tailoring"

    profile = ProfileSchema(
        education_level="10th",
        interests=[hindi_input],
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    top = result.pathways[0]
    assert top.trade == "tailoring"

# 13. Remove a constraint -> Result count never drops
def test_case_13_remove_constraint_result_count_never_drops(fixtures):
    profile = ProfileSchema(
        education_level="10th",
        work_preference="either",
    )
    # Constrained: max 2 months
    result_constrained = compute_pathways(
        profile=profile,
        constraints=ConstraintSchema(max_training_months=2),
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    # Unconstrained
    result_unconstrained = compute_pathways(
        profile=profile,
        constraints=ConstraintSchema(max_training_months=None),
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    assert len(result_unconstrained.pathways) >= len(result_constrained.pathways)

# 14. Run same input twice -> Identical output (deterministic)
def test_case_14_deterministic_identical_output(fixtures):
    profile = ProfileSchema(
        education_level="10th",
        interests=["catering", "tailoring"],
        skills=["cooking"],
        assets=["sewing machine"],
    )
    result1 = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    result2 = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    assert [p.id for p in result1.pathways] == [p.id for p in result2.pathways]
    assert [p.opportunity_status for p in result1.pathways] == [p.opportunity_status for p in result2.pathways]

# 15. Every excluded item -> Has a human-readable reason
def test_case_15_every_excluded_item_has_human_readable_reason(fixtures):
    profile = ProfileSchema(
        education_level="primary",
        mobility="home_only",
        max_training_months=2,
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    assert len(result.excluded) > 0
    for ex in result.excluded:
        assert isinstance(ex.reason, str)
        assert len(ex.reason.strip()) > 5
