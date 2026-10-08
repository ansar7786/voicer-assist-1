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
from typing import Any, Dict, List, Optional

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
    return {
        "status": "pong",
        "message": args.get("message", "pong"),
    }


def handle_update_profile(
    args: Dict[str, Any],
    session: SessionState,
) -> Dict[str, Any]:
    """
    Validate every argument, apply blocklist, normalise, then update session.
    Returns a tool-response dict: {"ok": True, "updated": [...]}
    or {"error": "...", "allowed_values": [...]} on validation failure.
    """
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


def handle_confirm_profile(
    args: Dict[str, Any],
    session: SessionState,
) -> Dict[str, Any]:
    """
    Validates summary_spoken is present, marks the profile confirmed.
    """
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


def _missing_priority(session: SessionState) -> List[str]:
    priority = [
        "education_level", "mobility", "max_training_months",
        "work_preference", "interests",
    ]
    return [f for f in priority if f not in session.profile or session.profile[f] is None]
