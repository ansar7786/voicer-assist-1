"""
Pure Python deterministic rule-based livelihood & skilling pathway engine for SIH26097.
Adheres strictly to PRD and Phase 2.1 specifications:
- Pure Python, zero network access, deterministic execution.
- Hard filters (FR-30) with human-readable rejection reasons for every excluded candidate.
- Delivery mode (home_based / centre_based / either) and equipment_obtainable filtering.
- Mobility filtering on training delivery:
  - home_only & within_village: allow only home_based or either qualifications.
  - within_block: requires a training centre for that trade in candidate's location_block.
  - anywhere: allows any centre in district.
- Minimum relevance rule: Low interest AND Low skill qualifications are excluded (allowing < 3 results).
- Factor labels (FR-31) High / Medium / Low / Unknown.
  - local_demand returns Unknown with "No demand data available".
- Deterministic ranking (FR-32) using config weights; ZERO numeric scores in output.
- Top 3 feasible pathways output (FR-33).
- Opportunity honesty (FR-34): "Sample opportunity: …" when is_sample is true, "Verified: …" only for verified non-sample, exactly "No verified opportunity found" if none exists.
- Recompute with diff (FR-35):
  - Items newly in top 3 state: "Moved into your top 3 because <removed pathway> no longer fits".
  - Kept items state the actual reason they stay feasible (not generic).
- No-result state (FR-38): complete reason listing when no pathway qualifies.
"""
import os
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from backend.schema import (
    ProfileSchema,
    ConstraintSchema,
    PathwaySchema,
    FactorSchema,
    CentreInfoSchema,
    ExcludedPathwaySchema,
    PathwaysResultSchema,
    DiffItemSchema,
    PathwayDiffSchema,
    RecomputeResultSchema,
)
from backend.normalize import (
    normalize_trade,
    normalize_skill,
    normalize_education,
    normalize_work_preference,
    normalize_mobility,
    normalize_asset,
)

CONFIG_PATH = Path(__file__).resolve().parent / "engine_config.yaml"

def load_engine_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {
        "weights": {
            "interest_match": 0.30,
            "skill_match": 0.25,
            "education_fit": 0.15,
            "duration_fit": 0.10,
            "local_demand": 0.10,
            "asset_fit": 0.10,
        },
        "thresholds": {"max_pathways": 3, "direct_skill_score": 1.0, "adjacent_skill_score": 0.6},
        "minimum_relevance": {"exclude_low_interest_and_low_skill": True},
        "education_levels": {
            "none": 0, "primary": 1, "8th": 2, "10th": 3, "12th": 4, "ITI": 5, "graduate": 6
        },
    }

def get_db_data() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load default dataset from SQLite database."""
    from backend.db import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM nsqf_qualifications")
    qualifications = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM training_centres")
    training_centres = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM opportunities")
    opportunities = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM skill_adjacency")
    skill_adjacency = [dict(r) for r in cur.fetchall()]

    conn.close()
    return qualifications, training_centres, opportunities, skill_adjacency

def check_hard_filters(
    qual: Dict[str, Any],
    profile: ProfileSchema,
    constraints: Optional[ConstraintSchema],
    edu_levels: Dict[str, int],
    training_centres: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """
    Evaluate hard filters (FR-30) including delivery mode and training mobility.
    Returns rejection reason string if excluded, else None.
    """
    # 1. Effective constraints (explicit constraints override profile)
    effective_max_months = None
    if constraints and constraints.max_training_months is not None:
        effective_max_months = constraints.max_training_months
    elif profile.max_training_months is not None:
        effective_max_months = profile.max_training_months

    effective_mobility = None
    if constraints and constraints.mobility:
        effective_mobility = normalize_mobility(constraints.mobility)
    elif profile.mobility:
        effective_mobility = normalize_mobility(profile.mobility)

    effective_work_pref = None
    if constraints and constraints.work_preference:
        effective_work_pref = normalize_work_preference(constraints.work_preference)
    elif profile.work_preference:
        effective_work_pref = normalize_work_preference(profile.work_preference)

    candidate_edu = normalize_education(profile.education_level)
    candidate_edu_val = edu_levels.get(candidate_edu, 0)

    # 2. Education Hard Filter
    entry_edu = normalize_education(qual.get("entry_education", "none"))
    entry_edu_val = edu_levels.get(entry_edu, 0)
    if candidate_edu_val < entry_edu_val:
        candidate_label = candidate_edu if candidate_edu != "none" else "no formal"
        return f"Requires at least {entry_edu} education; candidate has {candidate_label}"

    # 3. Mobility Hard Filter (filters on training delivery & job travel)
    delivery_mode = qual.get("delivery_mode", "either").lower()
    requires_travel = int(qual.get("requires_travel", 0))

    if effective_mobility in ["home_only", "within_village"]:
        mob_label = "home only" if effective_mobility == "home_only" else "within village only"
        if delivery_mode == "centre_based":
            return f"Requires centre-based training, but candidate is restricted to {mob_label}"
        if requires_travel == 1:
            return f"Requires travel for employment, but candidate is restricted to {mob_label}"
    elif effective_mobility == "within_block":
        user_block = profile.location_block
        if not user_block:
            if delivery_mode == "centre_based":
                return "Requires centre-based training in user's block, but no location block was provided"
        else:
            centres = training_centres or []
            has_centre = any(
                tc.get("trade") == qual.get("trade")
                and tc.get("block", "").strip().lower() == user_block.strip().lower()
                for tc in centres
            )
            if not has_centre and delivery_mode == "centre_based":
                return f"Requires a training centre in {user_block} for this trade, but none is available"
    elif effective_mobility == "anywhere":
        # Allows any centre in district
        pass

    # 4. Duration Hard Filter
    duration = int(qual.get("duration_months", 0))
    if effective_max_months is not None and duration > effective_max_months:
        return f"Requires {duration} months, exceeding your limit of {effective_max_months} months"

    # 5. Work Preference Hard Filter
    route_type = qual.get("route_type", "both").lower()
    self_suitable = int(qual.get("self_employment_suitable", 1))

    if effective_work_pref == "self":
        if route_type == "wage" or self_suitable == 0:
            return "Only suitable for wage employment, but candidate prefers self-employment"
    elif effective_work_pref == "wage":
        if route_type == "self":
            return "Only suitable for self-employment, but candidate prefers wage employment"

    return None

def compute_pathways(
    profile: ProfileSchema,
    constraints: Optional[ConstraintSchema] = None,
    qualifications: Optional[List[Dict[str, Any]]] = None,
    training_centres: Optional[List[Dict[str, Any]]] = None,
    opportunities: Optional[List[Dict[str, Any]]] = None,
    skill_adjacency: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> PathwaysResultSchema:
    """
    Deterministic rule-based pathway generator.
    """
    if config is None:
        config = load_engine_config()

    if qualifications is None or training_centres is None or opportunities is None or skill_adjacency is None:
        db_q, db_tc, db_opp, db_adj = get_db_data()
        qualifications = qualifications if qualifications is not None else db_q
        training_centres = training_centres if training_centres is not None else db_tc
        opportunities = opportunities if opportunities is not None else db_opp
        skill_adjacency = skill_adjacency if skill_adjacency is not None else db_adj

    weights = config.get("weights", {})
    thresholds = config.get("thresholds", {})
    min_relevance_cfg = config.get("minimum_relevance", {})
    exclude_low_rel = min_relevance_cfg.get("exclude_low_interest_and_low_skill", True)
    edu_levels = config.get("education_levels", {
        "none": 0, "primary": 1, "8th": 2, "10th": 3, "12th": 4, "ITI": 5, "graduate": 6
    })

    # Normalized profile attributes
    normalized_interests = [normalize_trade(i) for i in profile.interests if normalize_trade(i)]
    normalized_skills = [normalize_skill(s) for s in profile.skills if normalize_skill(s)]
    normalized_assets = [normalize_asset(a) for a in profile.assets if normalize_asset(a)]
    candidate_edu = normalize_education(profile.education_level)
    candidate_edu_val = edu_levels.get(candidate_edu, 0)
    has_interests_stated = len(profile.interests) > 0

    passed_qualifications = []
    excluded_pathways = []

    # 1. Hard Filtering
    for qual in qualifications:
        rejection_reason = check_hard_filters(
            qual, profile, constraints, edu_levels, training_centres=training_centres
        )
        if rejection_reason:
            excluded_pathways.append(
                ExcludedPathwaySchema(
                    id=qual["id"],
                    name=qual["qualification_name"],
                    trade=qual["trade"],
                    reason=rejection_reason,
                )
            )
        else:
            passed_qualifications.append(qual)

    # 2. Ranking & Factor Formulation (FR-31, FR-32)
    scored_candidates = []

    for qual in passed_qualifications:
        trade = qual["trade"]
        q_id = qual["id"]
        q_name = qual["qualification_name"]
        duration = int(qual.get("duration_months", 3))
        entry_edu = normalize_education(qual.get("entry_education", "none"))
        entry_edu_val = edu_levels.get(entry_edu, 0)
        equipment_needed = qual.get("equipment_needed", "").strip()
        delivery_mode = qual.get("delivery_mode", "either")
        equipment_obtainable = int(qual.get("equipment_obtainable", 1))

        # A. Interest match
        if not has_interests_stated:
            interest_score = 0.0
            interest_label = "Unknown"
            interest_reason = "No specific interests stated"
        elif trade in normalized_interests:
            interest_score = 1.0
            interest_label = "High"
            interest_reason = f"Matches your expressed interest in {trade}"
        else:
            interest_score = 0.0
            interest_label = "Low"
            interest_reason = f"Trade {trade} not among expressed interests"

        # B. Skill match via adjacency
        trade_adj = [adj for adj in skill_adjacency if adj.get("to_trade") == trade]
        direct_skills = [
            adj["from_skill"] for adj in trade_adj
            if adj.get("closeness") == "direct" and adj["from_skill"] in normalized_skills
        ]
        adjacent_skills = [
            adj["from_skill"] for adj in trade_adj
            if adj.get("closeness") == "adjacent" and adj["from_skill"] in normalized_skills
        ]

        if direct_skills:
            skill_score = thresholds.get("direct_skill_score", 1.0)
            skill_label = "High"
            skill_reason = f"Direct skill match with {', '.join(direct_skills)}"
        elif adjacent_skills:
            skill_score = thresholds.get("adjacent_skill_score", 0.6)
            skill_label = "Medium"
            skill_reason = f"Adjacent skill match ({', '.join(adjacent_skills)} relates to {trade})"
        else:
            skill_score = thresholds.get("unmatched_skill_score", 0.0)
            skill_label = "Low"
            skill_reason = "New domain; foundational training needed"

        # Minimum relevance check: Low interest AND Low skill -> exclude
        if exclude_low_rel and interest_label == "Low" and skill_label == "Low":
            excluded_pathways.append(
                ExcludedPathwaySchema(
                    id=q_id,
                    name=q_name,
                    trade=trade,
                    reason="Low interest match and no related skill match; does not meet minimum relevance threshold",
                )
            )
            continue

        # C. Education fit
        if candidate_edu_val > entry_edu_val:
            edu_score = 1.0
            edu_label = "High"
            edu_reason = f"Education level ({candidate_edu}) exceeds entry requirement ({entry_edu})"
        elif candidate_edu_val == entry_edu_val:
            edu_score = 1.0
            edu_label = "High"
            edu_reason = f"Education level ({candidate_edu}) meets required {entry_edu}"
        else:
            edu_score = 0.7
            edu_label = "Medium"
            edu_reason = f"Education aligns with qualification level"

        # D. Duration fit
        if duration <= 2:
            duration_score = 1.0
            duration_label = "High"
            duration_reason = f"Short duration course ({duration} months)"
        elif duration <= 3:
            duration_score = 0.8
            duration_label = "Medium"
            duration_reason = f"Standard duration course ({duration} months)"
        else:
            duration_score = 0.5
            duration_label = "Medium"
            duration_reason = f"Course duration is {duration} months"

        # E. Local demand (Returns Unknown with "No demand data available" until real data exists)
        demand_score = 0.5
        demand_label = "Unknown"
        demand_reason = "No demand data available"

        # F. Asset fit
        if equipment_needed and equipment_needed.lower() != "none":
            norm_needed = normalize_asset(equipment_needed)
            if norm_needed in normalized_assets or any(norm_needed in a for a in normalized_assets):
                asset_score = 1.0
                asset_label = "High"
                asset_reason = f"Candidate owns required equipment ({equipment_needed})"
            else:
                asset_score = 0.1
                asset_label = "Low"
                asset_reason = f"Requires equipment ({equipment_needed}) not currently owned"
        else:
            asset_score = 0.8
            asset_label = "Medium"
            asset_reason = "No special equipment required"

        # Compute internal composite score (used purely for sorting; NOT in output)
        composite_score = (
            weights.get("interest_match", 0.30) * interest_score
            + weights.get("skill_match", 0.25) * skill_score
            + weights.get("education_fit", 0.15) * edu_score
            + weights.get("duration_fit", 0.10) * duration_score
            + weights.get("local_demand", 0.10) * demand_score
            + weights.get("asset_fit", 0.10) * asset_score
        )

        # Urgency adjustment if income needed urgently: boost courses <= 2 months
        if profile.urgency_of_income == "urgent" and duration <= 2:
            composite_score += 0.05

        factors = [
            FactorSchema(factor="interest_match", label=interest_label, reason=interest_reason),
            FactorSchema(factor="skill_match", label=skill_label, reason=skill_reason),
            FactorSchema(factor="education_fit", label=edu_label, reason=edu_reason),
            FactorSchema(factor="duration_fit", label=duration_label, reason=duration_reason),
            FactorSchema(factor="local_demand", label=demand_label, reason=demand_reason),
            FactorSchema(factor="asset_fit", label=asset_label, reason=asset_reason),
        ]

        # Opportunity honesty (FR-34)
        trade_opps = [opp for opp in opportunities if opp.get("trade") == trade]
        if trade_opps:
            first_opp = trade_opps[0]
            is_sample = int(first_opp.get("is_sample", 0)) == 1
            is_verified = int(first_opp.get("verified", 0)) == 1
            note = first_opp.get("source_note", "Available opportunity")
            block = first_opp.get("block", "district")
            if is_sample:
                opportunity_status = f"Sample opportunity: {note} in {block}"
            elif is_verified:
                opportunity_status = f"Verified: {note} in {block}"
            else:
                opportunity_status = "No verified opportunity found"
        else:
            opportunity_status = "No verified opportunity found"

        # Nearest centre
        centres_for_trade = [tc for tc in training_centres if tc.get("trade") == trade]
        nearest_centre = None
        if centres_for_trade:
            loc_block = profile.location_block
            matched_c = next((c for c in centres_for_trade if loc_block and c.get("block") == loc_block), centres_for_trade[0])
            nearest_centre = CentreInfoSchema(
                name=matched_c["name"],
                block=matched_c["block"],
                seats=int(matched_c["seats"]),
                next_batch_date=matched_c.get("next_batch_date"),
                mode=matched_c.get("mode"),
            )

        # Skill gap calculation
        required_skills = [
            adj["from_skill"] for adj in trade_adj if adj.get("closeness") == "direct"
        ]
        missing_skills = [s for s in required_skills if s not in normalized_skills]

        pathway = PathwaySchema(
            id=q_id,
            name=q_name,
            trade=trade,
            route=qual.get("route_type", "both"),
            qualification=q_name,
            nsqf_level=int(qual.get("nsqf_level", 3)),
            duration_months=duration,
            delivery_mode=delivery_mode,
            equipment_obtainable=equipment_obtainable,
            skill_gap=missing_skills,
            nearest_centre=nearest_centre,
            opportunity_status=opportunity_status,
            factors=factors,
        )

        scored_candidates.append({
            "pathway": pathway,
            "composite_score": composite_score,
            "skill_score": skill_score,
            "duration": duration,
            "trade": trade,
            "name": q_name,
            "id": q_id,
        })

    # If no pathways passed both hard filters and minimum relevance, return no-result state (FR-38)
    if not scored_candidates:
        no_result_reasons = sorted(list({ex.reason for ex in excluded_pathways}))
        return PathwaysResultSchema(
            pathways=[],
            excluded=excluded_pathways,
            no_result_reasons=no_result_reasons,
        )

    # Deterministic tie-breaking sort:
    scored_candidates.sort(
        key=lambda x: (
            -round(x["composite_score"], 4),
            -round(x["skill_score"], 4),
            x["duration"],
            x["trade"],
            x["id"],
        )
    )

    max_pathways = thresholds.get("max_pathways", 3)
    top_candidates = scored_candidates[:max_pathways]
    top_pathways = [item["pathway"] for item in top_candidates]

    # Any candidate that passed hard filters but didn't make top 3 is logged in excluded with ranking reason
    unranked_candidates = scored_candidates[max_pathways:]
    for unranked in unranked_candidates:
        excluded_pathways.append(
            ExcludedPathwaySchema(
                id=unranked["id"],
                name=unranked["name"],
                trade=unranked["trade"],
                reason="Ranked lower than top alternative pathways for your profile",
            )
        )

    return PathwaysResultSchema(
        pathways=top_pathways,
        excluded=excluded_pathways,
        no_result_reasons=[],
    )

def recompute_pathways(
    profile: ProfileSchema,
    previous_pathway_ids: List[str],
    constraints: Optional[ConstraintSchema] = None,
    qualifications: Optional[List[Dict[str, Any]]] = None,
    training_centres: Optional[List[Dict[str, Any]]] = None,
    opportunities: Optional[List[Dict[str, Any]]] = None,
    skill_adjacency: Optional[List[Dict[str, Any]]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> RecomputeResultSchema:
    """
    Recompute pathways and compute a transparent diff (FR-35).
    """
    result = compute_pathways(
        profile=profile,
        constraints=constraints,
        qualifications=qualifications,
        training_centres=training_centres,
        opportunities=opportunities,
        skill_adjacency=skill_adjacency,
        config=config,
    )

    new_pathway_map = {p.id: p for p in result.pathways}
    new_ids = [p.id for p in result.pathways]
    old_ids = list(previous_pathway_ids)

    # Excluded map for reasons
    excluded_map = {ex.id: ex for ex in result.excluded}

    removed = []
    for p_id in old_ids:
        if p_id not in new_pathway_map:
            if p_id in excluded_map:
                ex = excluded_map[p_id]
                removed.append(DiffItemSchema(id=ex.id, name=ex.name, trade=ex.trade, reason=ex.reason))
            else:
                removed.append(DiffItemSchema(id=p_id, name="Previous Pathway", trade="", reason="Excluded under updated constraints"))

    removed_names = [r.name for r in removed]

    added = []
    kept = []

    for p_id in new_ids:
        p = new_pathway_map[p_id]
        if p_id in old_ids:
            # Replace the generic "kept" reason with the actual reason it stays feasible
            reasons = []
            if constraints and constraints.max_training_months is not None:
                reasons.append(f"{p.duration_months} months course duration is within your {constraints.max_training_months} months limit")
            elif profile.max_training_months is not None:
                reasons.append(f"{p.duration_months} months course duration fits within your limit")

            if constraints and constraints.mobility:
                reasons.append(f"{p.delivery_mode.replace('_', ' ')} training fits your {constraints.mobility.replace('_', ' ')} preference")
            elif profile.mobility:
                reasons.append(f"{p.delivery_mode.replace('_', ' ')} training fits your {profile.mobility.replace('_', ' ')} preference")

            if constraints and constraints.work_preference:
                reasons.append(f"{p.route} route satisfies {constraints.work_preference} work preference")

            if not reasons:
                reasons.append(f"Meets all criteria and maintains strong relevance for {p.trade}")

            kept_reason = "; ".join(reasons)
            kept.append(DiffItemSchema(id=p.id, name=p.name, trade=p.trade, reason=kept_reason))
        else:
            # Newly entered top 3
            if removed_names:
                rem_str = ", ".join(removed_names)
                added_reason = f"Moved into your top 3 because {rem_str} no longer fits"
            else:
                added_reason = "Newly entered your top 3 under updated preferences"
            added.append(DiffItemSchema(id=p.id, name=p.name, trade=p.trade, reason=added_reason))

    return RecomputeResultSchema(
        pathways=result.pathways,
        excluded=result.excluded,
        diff=PathwayDiffSchema(added=added, removed=removed, kept=kept),
    )
