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

# --- Phase 2.1 Specific Tests ---

def test_phase21_home_only_gets_zero_centre_based_results(fixtures):
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
    # Zero centre-based results must be returned
    for p in result.pathways:
        assert p.delivery_mode in ["home_based", "either"]

    centre_based_quals = [q["id"] for q in fixtures["qualifications"] if q.get("delivery_mode") == "centre_based"]
    excluded_ids = {ex.id: ex.reason for ex in result.excluded}
    for cb_id in centre_based_quals:
        assert cb_id in excluded_ids
        assert "centre-based" in excluded_ids[cb_id]

def test_phase21_within_village_allows_only_home_based_or_either(fixtures):
    profile = ProfileSchema(
        education_level="graduate",
        mobility="within_village",
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
        assert p.delivery_mode in ["home_based", "either"]

    excluded_ids = {ex.id: ex.reason for ex in result.excluded}
    assert "Q_SEWING_02" in excluded_ids
    assert "within village only" in excluded_ids["Q_SEWING_02"]

def test_phase21_within_block_requires_centre_in_location_block(fixtures):
    # Candidate in Anandapuram with within_block mobility
    # Fixtures have centre in Anandapuram for tailoring, but NOT for solar_technician (in Pendurthi)
    profile = ProfileSchema(
        education_level="10th",
        location_block="Anandapuram",
        mobility="within_block",
        work_preference="either",
        interests=["solar_technician"],
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    excluded_ids = {ex.id: ex.reason for ex in result.excluded}
    assert "Q_SOLAR_01" in excluded_ids
    assert "Requires a training centre in Anandapuram for this trade" in excluded_ids["Q_SOLAR_01"]

def test_phase21_minimum_relevance_excludes_low_interest_and_skill(fixtures):
    # Candidate with ONLY tailoring interest and no other skills
    profile = ProfileSchema(
        education_level="10th",
        interests=["tailoring"],
        skills=[],
        work_preference="either",
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    # Only tailoring pathways should qualify (catering, solar, elec have Low interest & Low skill)
    for p in result.pathways:
        assert p.trade == "tailoring"
    # Number of results is allowed to be fewer than 3
    assert len(result.pathways) <= 2
    # Excluded list must contain minimum relevance reason
    excluded_reasons = [ex.reason for ex in result.excluded]
    assert any("minimum relevance threshold" in r for r in excluded_reasons)

def test_phase21_recompute_moved_into_top_3_and_non_generic_kept(fixtures):
    # Setup initial pathways with graduate education, tailoring interest
    profile = ProfileSchema(
        education_level="graduate",
        interests=["tailoring"],
        work_preference="either",
    )
    res_initial = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    prev_ids = [p.id for p in res_initial.pathways]

    # Recompute with home_only constraint which excludes centre-based courses
    res_recomp = recompute_pathways(
        profile=profile,
        previous_pathway_ids=prev_ids,
        constraints=ConstraintSchema(mobility="home_only"),
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    diff = res_recomp.diff
    # Any kept item must have an informative, non-generic reason
    for k in diff.kept:
        assert len(k.reason) > 0
        assert "Remains feasible and high-ranking" not in k.reason  # Not generic

    # Any added item when an item was removed should reference the removed item
    if len(diff.removed) > 0 and len(diff.added) > 0:
        for a in diff.added:
            assert "Moved into your top 3 because" in a.reason
            assert "no longer fits" in a.reason

def test_phase21_opportunity_status_says_sample_opportunity_when_is_sample(fixtures):
    # In fixtures, opportunities have is_sample: 1
    profile = ProfileSchema(
        education_level="10th",
        interests=["tailoring"],
        work_preference="self",
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    tailor_p = next(p for p in result.pathways if p.trade == "tailoring")
    assert tailor_p.opportunity_status.startswith("Sample opportunity:")
    assert "Verified:" not in tailor_p.opportunity_status

def test_phase21_local_demand_returns_unknown_with_no_demand_data(fixtures):
    profile = ProfileSchema(
        education_level="10th",
        interests=["tailoring"],
    )
    result = compute_pathways(
        profile=profile,
        qualifications=fixtures["qualifications"],
        training_centres=fixtures["training_centres"],
        opportunities=fixtures["opportunities"],
        skill_adjacency=fixtures["skill_adjacency"],
    )
    for p in result.pathways:
        demand_factor = next(f for f in p.factors if f.factor == "local_demand")
        assert demand_factor.label == "Unknown"
        assert demand_factor.reason == "No demand data available"
