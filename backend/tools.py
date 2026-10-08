"""
Tool declarations and handlers for SIH26097 Voice Assistant (Phase 4).

Declares:
  - ping           : NON_BLOCKING/SILENT (unchanged from Phase 3)
  - update_profile : NON_BLOCKING / scheduling SILENT
  - confirm_profile: BLOCKING

Every argument is validated; invalid enum values return a recoverable
tool error that tells the model exactly which values are allowed.

Skills, interests, and current_or_past_work are passed through
normalize.py; unknown terms are stored as free-text flagged
unmapped=True and never feed ranking.

The blocklist filter runs on all free-text fields; blocked text is
dropped silently (only "blocked field" is logged, never the content).
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from backend.session_store import (
    SessionState,
    VALID_EDUCATION_LEVELS,
    VALID_MOBILITY,
    VALID_WORK_PREFERENCE,
    VALID_TIME_AVAILABLE,
    VALID_URGENCY,
)
from backend.normalize import (
    normalize_skill,
    normalize_trade,
    normalize_education,
    normalize_mobility,
    normalize_work_preference,
    normalize_asset,
    ASSET_SYNONYMS,
)
from backend.blocklist import check_blocked

# ---------------------------------------------------------------------------
# Tool declarations (google-genai FunctionDeclaration format)
# ---------------------------------------------------------------------------

PING_DECLARATION = {
    "name": "ping",
    "description": (
        "A dummy tool for connectivity verification. "
        "Call when the user says 'ping' or asks to test tools."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "message": {
                "type": "STRING",
                "description": "Optional ping message from user",
            }
        },
    },
    # NON_BLOCKING with SILENT scheduling (no spoken acknowledgement)
    "behavior": "NON_BLOCKING",
    "scheduling": "SILENT",
}

UPDATE_PROFILE_DECLARATION = {
    "name": "update_profile",
    "description": (
        "Update one or more profile fields as the user speaks. "
        "Call silently whenever a new fact is clearly stated or strongly inferred. "
        "Do NOT call with uncertain values; wait until reasonably confident. "
        "Fields: education_level, skills (list), interests (list), "
        "current_or_past_work (string), mobility, max_training_months (int), "
        "time_available, work_preference, urgency_of_income, location_block, "
        "language, assets (list). "
        "Invalid enum values will be rejected with a recoverable error."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "education_level": {
                "type": "STRING",
                "description": (
                    "Educational qualification. "
                    "Allowed: none, primary, 8th, 10th, 12th, ITI, graduate"
                ),
            },
            "skills": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Skills the person already has (Telugu, Hindi, or English)",
            },
            "interests": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Trades or domains the person wants to learn",
            },
            "current_or_past_work": {
                "type": "STRING",
                "description": "Brief description of current or recent work",
            },
            "mobility": {
                "type": "STRING",
                "description": (
                    "How far person can travel for training. "
                    "Allowed: home_only, within_village, within_block, anywhere"
                ),
            },
            "max_training_months": {
                "type": "INTEGER",
                "description": "Maximum training duration in months (1–24)",
            },
            "time_available": {
                "type": "STRING",
                "description": (
                    "When person is free for training. "
                    "Allowed: full_time, part_time, weekends"
                ),
            },
            "work_preference": {
                "type": "STRING",
                "description": (
                    "Preferred work type. Allowed: self, wage, either"
                ),
            },
            "urgency_of_income": {
                "type": "STRING",
                "description": (
                    "How urgently person needs income. "
                    "Allowed: urgent, moderate, flexible"
                ),
            },
            "location_block": {
                "type": "STRING",
                "description": "Name of the block/mandal where person lives",
            },
            "language": {
                "type": "STRING",
                "description": "Conversation language code: te, hi, or en",
            },
            "assets": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Physical assets the person owns (e.g. sewing machine)",
            },
            "confidence": {
                "type": "STRING",
                "description": (
                    "How certain you are about these values. "
                    "Allowed: stated (person said it clearly), inferred (deduced from context). "
                    "Default: stated"
                ),
            },
        },
    },
    "behavior": "NON_BLOCKING",
    "scheduling": "SILENT",
}

CONFIRM_PROFILE_DECLARATION = {
    "name": "confirm_profile",
    "description": (
        "Call ONLY after reading the complete profile back to the user "
        "in simple words and the user explicitly says yes or confirms. "
        "This marks the profile as confirmed and enables pathway matching. "
        "Do not call this unless the user has clearly agreed."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "summary_spoken": {
                "type": "STRING",
                "description": (
                    "The exact summary sentence(s) you just read aloud to the user "
                    "before they confirmed. Required."
                ),
            },
        },
        "required": ["summary_spoken"],
    },
    "behavior": "BLOCKING",
}

GET_PATHWAYS_DECLARATION = {
    "name": "get_pathways",
    "description": (
        "Fetch top 3 feasible livelihood and skill training pathways based on the user's profile. "
        "Call when the user asks to see pathways or right after profile confirmation. "
        "Returns short structured text with pathway names, durations, one-line reasons, and opportunity status."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "location_block": {
                "type": "STRING",
                "description": "Optional location block for center proximity matching",
            },
        },
    },
    "behavior": "BLOCKING",
}

SET_CONSTRAINT_DECLARATION = {
    "name": "set_constraint",
    "description": (
        "Set what-if constraints (e.g. max_training_months, mobility, work_preference, time_available) "
        "or reset them, and recompute pathways with an immediate diff explaining which pathways dropped, "
        "were added, or were kept and why. Call when user states a restriction (e.g. 'cannot travel', "
        "'max 3 months', 'prefer wage work') or asks to reset."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "max_training_months": {
                "type": "INTEGER",
                "description": "Maximum training duration in months (1 to 12)",
            },
            "mobility": {
                "type": "STRING",
                "description": "Allowed travel: home_only, within_village, within_block, anywhere",
            },
            "work_preference": {
                "type": "STRING",
                "description": "Preferred work route: self, wage, either",
            },
            "time_available": {
                "type": "STRING",
                "description": "Time availability: full_time, part_time, weekends",
            },
            "reset": {
                "type": "BOOLEAN",
                "description": "Set to true to clear all constraints back to baseline",
            },
        },
    },
    "behavior": "BLOCKING",
}


# ---------------------------------------------------------------------------
# Normalise a list of free-text terms (skills, interests, assets)
# ---------------------------------------------------------------------------

def _normalise_list(
    field_name: str,
    raw_list: List[str],
) -> tuple[List[str], List[Dict[str, str]]]:
    """
    Returns (canonical_tags, unmapped_items).

    canonical_tags : list of known canonical strings (fed to ranking)
    unmapped_items : list of {"original": x, "stored": x, "unmapped": True}
                     (stored as free-text, never fed to ranking)
    """
    canonical: List[str] = []
    unmapped: List[Dict[str, str]] = []

    for raw in raw_list:
        if not raw or not raw.strip():
            continue
        blocked, reason = check_blocked(field_name, raw)
        if blocked:
            continue  # drop silently; blocklist already logged

        normed: Optional[str] = None
        if field_name == "interests":
            normed = normalize_trade(raw)
        elif field_name == "skills":
            normed = normalize_skill(raw)
        elif field_name == "assets":
            normed_asset = normalize_asset(raw)
            normed = normed_asset if (normed_asset and normed_asset in ASSET_SYNONYMS) else None
        else:
            normed = normalize_skill(raw) or normalize_trade(raw)

        if normed:
            if normed not in canonical:
                canonical.append(normed)
        else:
            unmapped.append({"original": raw.strip(), "stored": raw.strip(), "unmapped": True})

    return canonical, unmapped


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_ping(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return {
            "status": "pong",
            "message": args.get("message", "pong"),
        }
    except Exception:
        return {
            "error": "tool_error",
            "message": "ping execution failed",
            "recoverable": True,
        }


def _do_update_profile(
    args: Dict[str, Any],
    session: SessionState,
) -> Dict[str, Any]:
    if session.is_rate_limited():
        return {
            "error": "rate_limited",
            "message": "Too many updates. Please slow down.",
        }

    confidence = args.get("confidence", "stated")
    if confidence not in {"stated", "inferred"}:
        return {
            "error": "validation_failed",
            "details": [{
                "error": "invalid_enum",
                "field": "confidence",
                "allowed_values": ["stated", "inferred"],
            }],
        }

    errors = []
    updated_fields = []

    # -- education_level --
    if "education_level" in args and args["education_level"] is not None:
        raw = str(args["education_level"])
        blocked, _ = check_blocked("education_level", raw)
        if not blocked:
            normed = normalize_education(raw)
            # normalize_education returns "none" as fallback for unrecognized input.
            # We must distinguish intentional "none" (illiterate) from unknown input.
            # Check: if the raw term is not literally "none" / a known synonym AND
            # the result is "none", treat it as unrecognized → reject.
            from backend.normalize import EDUCATION_SYNONYMS, clean_input
            raw_clean = clean_input(raw)
            recognized = False
            for level, syns in EDUCATION_SYNONYMS.items():
                if raw_clean == level.lower():
                    recognized = True
                    break
                for syn in syns:
                    from backend.normalize import _matches_pattern
                    if _matches_pattern(syn, raw_clean):
                        recognized = True
                        break
                if recognized:
                    break
            if not recognized:
                errors.append({
                    "error": "invalid_enum",
                    "field": "education_level",
                    "allowed_values": sorted(VALID_EDUCATION_LEVELS),
                })
            else:
                diff = session.update_field("education_level", normed, "voice", confidence)
                if diff:
                    updated_fields.append("education_level")

    # -- mobility --
    if "mobility" in args and args["mobility"] is not None:
        raw = str(args["mobility"])
        normed = normalize_mobility(raw)
        if normed is None:
            # Try exact canonical match
            if raw in VALID_MOBILITY:
                normed = raw
            else:
                errors.append({
                    "error": "invalid_enum",
                    "field": "mobility",
                    "allowed_values": sorted(VALID_MOBILITY),
                })
        if normed is not None and normed in VALID_MOBILITY:
            diff = session.update_field("mobility", normed, "voice", confidence)
            if diff:
                updated_fields.append("mobility")

    # -- work_preference --
    if "work_preference" in args and args["work_preference"] is not None:
        raw = str(args["work_preference"])
        normed = normalize_work_preference(raw)
        if normed is None:
            if raw in VALID_WORK_PREFERENCE:
                normed = raw
            else:
                errors.append({
                    "error": "invalid_enum",
                    "field": "work_preference",
                    "allowed_values": sorted(VALID_WORK_PREFERENCE),
                })
        if normed is not None and normed in VALID_WORK_PREFERENCE:
            diff = session.update_field("work_preference", normed, "voice", confidence)
            if diff:
                updated_fields.append("work_preference")

    # -- time_available --
    if "time_available" in args and args["time_available"] is not None:
        val = str(args["time_available"])
        if val not in VALID_TIME_AVAILABLE:
            errors.append({
                "error": "invalid_enum",
                "field": "time_available",
                "allowed_values": sorted(VALID_TIME_AVAILABLE),
            })
        else:
            diff = session.update_field("time_available", val, "voice", confidence)
            if diff:
                updated_fields.append("time_available")

    # -- urgency_of_income --
    if "urgency_of_income" in args and args["urgency_of_income"] is not None:
        val = str(args["urgency_of_income"])
        if val not in VALID_URGENCY:
            errors.append({
                "error": "invalid_enum",
                "field": "urgency_of_income",
                "allowed_values": sorted(VALID_URGENCY),
            })
        else:
            diff = session.update_field("urgency_of_income", val, "voice", confidence)
            if diff:
                updated_fields.append("urgency_of_income")

    # -- max_training_months --
    if "max_training_months" in args and args["max_training_months"] is not None:
        try:
            months = int(args["max_training_months"])
            if months < 1 or months > 24:
                errors.append({
                    "error": "out_of_range",
                    "field": "max_training_months",
                    "message": "Value must be between 1 and 24",
                })
            else:
                diff = session.update_field("max_training_months", months, "voice", confidence)
                if diff:
                    updated_fields.append("max_training_months")
        except (ValueError, TypeError):
            errors.append({
                "error": "invalid_type",
                "field": "max_training_months",
                "message": "Must be an integer",
            })

    # -- language --
    if "language" in args and args["language"] is not None:
        lang = str(args["language"]).lower()
        if lang not in {"te", "hi", "en"}:
            errors.append({
                "error": "invalid_enum",
                "field": "language",
                "allowed_values": ["te", "hi", "en"],
            })
        else:
            diff = session.update_field("language", lang, "voice", confidence)
            if diff:
                updated_fields.append("language")

    # -- location_block --
    if "location_block" in args and args["location_block"] is not None:
        raw = str(args["location_block"]).strip()
        blocked, _ = check_blocked("location_block", raw)
        if not blocked and raw:
            diff = session.update_field("location_block", raw, "voice", confidence)
            if diff:
                updated_fields.append("location_block")

    # -- current_or_past_work --
    if "current_or_past_work" in args and args["current_or_past_work"] is not None:
        raw = str(args["current_or_past_work"]).strip()
        blocked, _ = check_blocked("current_or_past_work", raw)
        if not blocked and raw:
            # Try to normalise to trade tag, else store as free text
            normed_trade = normalize_trade(raw)
            stored_val = normed_trade if normed_trade else raw
            diff = session.update_field("current_or_past_work", stored_val, "voice", confidence)
            if diff:
                updated_fields.append("current_or_past_work")

    # -- skills (list) --
    if "skills" in args and args["skills"] is not None:
        raw_list = args["skills"] if isinstance(args["skills"], list) else [args["skills"]]
        canonical, unmapped = _normalise_list("skills", raw_list)
        combined = canonical + [u["stored"] for u in unmapped]
        existing = session.profile.get("skills", [])
        merged = list(dict.fromkeys(existing + combined))
        diff = session.update_field("skills", merged, "voice", confidence)
        if diff:
            updated_fields.append("skills")
        if unmapped:
            # Track unmapped separately for ProfileCard display
            existing_um = session.profile.get("_skills_unmapped", [])
            session.profile["_skills_unmapped"] = existing_um + [u["stored"] for u in unmapped]

    # -- interests (list) --
    if "interests" in args and args["interests"] is not None:
        raw_list = args["interests"] if isinstance(args["interests"], list) else [args["interests"]]
        canonical, unmapped = _normalise_list("interests", raw_list)
        combined = canonical + [u["stored"] for u in unmapped]
        existing = session.profile.get("interests", [])
        merged = list(dict.fromkeys(existing + combined))
        diff = session.update_field("interests", merged, "voice", confidence)
        if diff:
            updated_fields.append("interests")
        if unmapped:
            existing_um = session.profile.get("_interests_unmapped", [])
            session.profile["_interests_unmapped"] = existing_um + [u["stored"] for u in unmapped]

    # -- assets (list) --
    if "assets" in args and args["assets"] is not None:
        raw_list = args["assets"] if isinstance(args["assets"], list) else [args["assets"]]
        canonical, unmapped = _normalise_list("assets", raw_list)
        combined = canonical + [u["stored"] for u in unmapped]
        existing = session.profile.get("assets", [])
        merged = list(dict.fromkeys(existing + combined))
        diff = session.update_field("assets", merged, "voice", confidence)
        if diff:
            updated_fields.append("assets")

    # If there were any validation errors, return the first one as recoverable
    if errors:
        return {"error": "validation_failed", "details": errors}

    return {"ok": True, "updated": updated_fields}


def handle_update_profile(
    args: Dict[str, Any],
    session: SessionState,
) -> Dict[str, Any]:
    """
    Validate every argument, apply blocklist, normalise, then update session.
    Returns a tool-response dict: {"ok": True, "updated": [...]}
    or {"error": "...", "allowed_values": [...]} on validation failure.
    """
    try:
        return _do_update_profile(args, session)
    except Exception:
        return {
            "error": "tool_error",
            "message": "update_profile execution failed",
            "recoverable": True,
        }


def handle_confirm_profile(
    args: Dict[str, Any],
    session: SessionState,
) -> Dict[str, Any]:
    """
    Validates summary_spoken is present, marks the profile confirmed.
    """
    try:
        summary = args.get("summary_spoken", "").strip()
        if not summary:
            return {
                "error": "missing_required",
                "field": "summary_spoken",
                "message": "summary_spoken is required and must not be empty",
            }

        if not session.profile:
            return {
                "error": "empty_profile",
                "message": (
                    "No profile fields have been collected yet. "
                    "Please gather education_level, mobility, and interests first."
                ),
            }

        session.set_confirmed()
        return {
            "ok": True,
            "confirmed": True,
            "profile_fields_count": len([
                k for k in session.profile
                if not k.startswith("_")
            ]),
            # High-priority fields not yet captured
            "missing_priority_fields": _missing_priority(session),
        }
    except Exception:
        return {
            "error": "tool_error",
            "message": "confirm_profile execution failed",
            "recoverable": True,
        }


def _missing_priority(session: SessionState) -> List[str]:
    priority = [
        "education_level", "mobility", "max_training_months",
        "work_preference", "interests",
    ]
    return [f for f in priority if f not in session.profile or session.profile[f] is None]


def handle_get_pathways(args: Dict[str, Any], session: SessionState) -> Dict[str, Any]:
    from backend.schema import ProfileSchema, ConstraintSchema
    from backend.engine import compute_pathways

    try:
        is_unconfirmed = not session.confirmed

        clean_profile = {k: v for k, v in session.profile.items() if not k.startswith("_")}
        if args.get("location_block"):
            clean_profile["location_block"] = args["location_block"].strip()

        profile_obj = ProfileSchema(**clean_profile)
        constraints_obj = ConstraintSchema(**session.constraints) if session.constraints else None

        result = compute_pathways(profile_obj, constraints_obj)
        session.previous_pathways = result.pathways

        # Build short structured text summary (NO scores!)
        lines = []
        if is_unconfirmed:
            lines.append("UNCONFIRMED PREVIEW (profile summary not yet confirmed by user):")

        if not result.pathways:
            lines.append("No feasible pathways found matching your current profile.")
            if result.excluded:
                lines.append(f"Excluded: {len(result.excluded)} qualifications did not match your constraints.")
        else:
            for i, p in enumerate(result.pathways, 1):
                factor_reasons = [f.reason for f in p.factors if f.label in ("High", "Medium") and f.reason]
                one_line_reason = factor_reasons[0] if factor_reasons else f"Strong overall fit for {p.trade}"
                opp_status = getattr(p, "opportunity_status", None) or "No verified opportunity found"
                lines.append(
                    f"{i}. {p.trade.title()} - {p.name} ({p.duration_months} mo): "
                    f"{one_line_reason}. Opportunity: {opp_status}"
                )

        summary_text = "\n".join(lines)

        return {
            "ok": True,
            "unconfirmed": is_unconfirmed,
            "pathways_summary": summary_text,
            "text": summary_text,
            "pathways": [p.model_dump() for p in result.pathways],
            "excluded": [e.model_dump() for e in result.excluded],
            "count": len(result.pathways),
        }
    except Exception as e:
        logger.error("EVENT: tool_error | tool: get_pathways | exc: %s", type(e).__name__)
        return {
            "error": "tool_error",
            "message": "get_pathways execution failed",
            "text": "get_pathways execution failed",
            "recoverable": True,
        }


def handle_set_constraint(args: Dict[str, Any], session: SessionState) -> Dict[str, Any]:
    from backend.schema import ProfileSchema, ConstraintSchema
    from backend.engine import recompute_pathways

    try:
        is_reset = bool(args.get("reset"))
        if is_reset:
            session.constraints = {}
        else:
            if "max_training_months" in args and args["max_training_months"] is not None:
                m = args["max_training_months"]
                if not isinstance(m, int) or m < 1 or m > 12:
                    return {
                        "error": "invalid_value",
                        "field": "max_training_months",
                        "message": "max_training_months must be an integer between 1 and 12",
                        "text": "max_training_months must be an integer between 1 and 12",
                        "recoverable": True,
                    }
                session.constraints["max_training_months"] = m

            if "mobility" in args and args["mobility"]:
                norm_mob = normalize_mobility(args["mobility"]) or args["mobility"]
                if norm_mob not in VALID_MOBILITY:
                    return {
                        "error": "invalid_value",
                        "field": "mobility",
                        "message": f"mobility must be one of: {sorted(VALID_MOBILITY)}",
                        "text": f"Invalid mobility. Must be one of: {sorted(VALID_MOBILITY)}",
                        "allowed_values": sorted(VALID_MOBILITY),
                        "recoverable": True,
                    }
                session.constraints["mobility"] = norm_mob

            if "work_preference" in args and args["work_preference"]:
                norm_wp = normalize_work_preference(args["work_preference"]) or args["work_preference"]
                if norm_wp not in VALID_WORK_PREFERENCE:
                    return {
                        "error": "invalid_value",
                        "field": "work_preference",
                        "message": f"work_preference must be one of: {sorted(VALID_WORK_PREFERENCE)}",
                        "text": f"Invalid work_preference. Must be one of: {sorted(VALID_WORK_PREFERENCE)}",
                        "allowed_values": sorted(VALID_WORK_PREFERENCE),
                        "recoverable": True,
                    }
                session.constraints["work_preference"] = norm_wp

            if "time_available" in args and args["time_available"]:
                ta = str(args["time_available"]).strip().lower()
                if ta not in VALID_TIME_AVAILABLE:
                    return {
                        "error": "invalid_value",
                        "field": "time_available",
                        "message": f"time_available must be one of: {sorted(VALID_TIME_AVAILABLE)}",
                        "text": f"Invalid time_available. Must be one of: {sorted(VALID_TIME_AVAILABLE)}",
                        "allowed_values": sorted(VALID_TIME_AVAILABLE),
                        "recoverable": True,
                    }
                session.constraints["time_available"] = ta

        clean_profile = {k: v for k, v in session.profile.items() if not k.startswith("_")}
        profile_obj = ProfileSchema(**clean_profile)
        constraints_obj = ConstraintSchema(**session.constraints) if session.constraints else None

        previous_ids = [p.id for p in session.previous_pathways] if session.previous_pathways else []

        result = recompute_pathways(
            profile=profile_obj,
            previous_pathway_ids=previous_ids,
            constraints=constraints_obj,
        )
        session.previous_pathways = result.pathways

        # Build short structured diff summary text (NO scores!)
        lines = []
        if is_reset:
            lines.append("Reset all simulated constraints.")
        lines.append("Diff summary:")
        if result.diff.removed:
            lines.append("Dropped:")
            for item in result.diff.removed:
                lines.append(f"- {item.name}: {item.reason}")
        if result.diff.added:
            lines.append("Added to top 3:")
            for item in result.diff.added:
                lines.append(f"- {item.name}: {item.reason}")
        if result.diff.kept:
            lines.append("Kept:")
            for item in result.diff.kept:
                lines.append(f"- {item.name}: {item.reason}")

        lines.append("Current Top Pathways:")
        for i, p in enumerate(result.pathways, 1):
            opp_status = getattr(p, "opportunity_status", None) or "No verified opportunity found"
            lines.append(f"{i}. {p.trade.title()} - {p.name} ({p.duration_months} mo). Opportunity: {opp_status}")

        summary_text = "\n".join(lines)

        return {
            "ok": True,
            "diff_summary": summary_text,
            "text": summary_text,
            "diff": result.diff.model_dump(),
            "pathways": [p.model_dump() for p in result.pathways],
            "excluded": [e.model_dump() for e in result.excluded],
            "constraints": session.constraints,
        }
    except Exception as e:
        logger.error("EVENT: tool_error | tool: set_constraint | exc: %s", type(e).__name__)
        return {
            "error": "tool_error",
            "message": "set_constraint execution failed",
            "recoverable": True,
        }
