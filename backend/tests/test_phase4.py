"""
Phase 4 tests: tool argument validation, blocklist (EN/TE/HI),
normalizer integration, idempotency, and the rule that transcripts
are NEVER persisted to the database.
"""
import json
import sqlite3
import pytest

from backend.session_store import create_session, VALID_EDUCATION_LEVELS, VALID_MOBILITY
from backend.tools import handle_update_profile, handle_confirm_profile, handle_ping
from backend.blocklist import check_blocked

# ──────────────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────────────

def new_session():
    return create_session(language="te")


# ══════════════════════════════════════════════════════════════════════════════
# 1. Ping handler
# ══════════════════════════════════════════════════════════════════════════════

def test_ping_returns_pong():
    result = handle_ping({})
    assert result["status"] == "pong"


def test_ping_echoes_message():
    result = handle_ping({"message": "hello"})
    assert result["message"] == "hello"


# ══════════════════════════════════════════════════════════════════════════════
# 2. update_profile — enum validation
# ══════════════════════════════════════════════════════════════════════════════

def test_valid_education_level_accepted():
    sess = new_session()
    for level in VALID_EDUCATION_LEVELS:
        sess2 = new_session()
        r = handle_update_profile({"education_level": level}, sess2)
        assert r.get("ok") is True, f"education_level '{level}' rejected: {r}"


def test_invalid_education_level_rejected():
    sess = new_session()
    r = handle_update_profile({"education_level": "phd"}, sess)
    assert r.get("error") == "validation_failed"
    detail = r["details"][0]
    assert detail["field"] == "education_level"
    assert "allowed_values" in detail


def test_valid_mobility_accepted():
    for mob in VALID_MOBILITY:
        sess = new_session()
        r = handle_update_profile({"mobility": mob}, sess)
        assert r.get("ok") is True, f"mobility '{mob}' rejected: {r}"


def test_invalid_mobility_rejected():
    sess = new_session()
    r = handle_update_profile({"mobility": "underwater"}, sess)
    assert r.get("error") == "validation_failed"
    detail = r["details"][0]
    assert detail["field"] == "mobility"
    assert "allowed_values" in detail
    for val in ["home_only", "within_village", "within_block", "anywhere"]:
        assert val in detail["allowed_values"]


def test_invalid_work_preference_rejected():
    sess = new_session()
    r = handle_update_profile({"work_preference": "gig_economy"}, sess)
    assert r.get("error") == "validation_failed"


def test_invalid_time_available_rejected():
    sess = new_session()
    r = handle_update_profile({"time_available": "sometimes"}, sess)
    assert r.get("error") == "validation_failed"


def test_invalid_urgency_rejected():
    sess = new_session()
    r = handle_update_profile({"urgency_of_income": "eventually"}, sess)
    assert r.get("error") == "validation_failed"


def test_invalid_confidence_rejected():
    sess = new_session()
    r = handle_update_profile({"education_level": "10th", "confidence": "guessed"}, sess)
    assert r.get("error") == "validation_failed"


def test_max_training_months_out_of_range():
    sess = new_session()
    r = handle_update_profile({"max_training_months": 0}, sess)
    assert r.get("error") == "validation_failed"

    sess2 = new_session()
    r2 = handle_update_profile({"max_training_months": 25}, sess2)
    assert r2.get("error") == "validation_failed"


def test_max_training_months_valid():
    sess = new_session()
    r = handle_update_profile({"max_training_months": 6}, sess)
    assert r.get("ok") is True
    assert sess.profile["max_training_months"] == 6


def test_invalid_language_rejected():
    sess = new_session()
    r = handle_update_profile({"language": "french"}, sess)
    assert r.get("error") == "validation_failed"


def test_valid_language_accepted():
    for lang in ("te", "hi", "en"):
        sess = new_session()
        r = handle_update_profile({"language": lang}, sess)
        assert r.get("ok") is True


# ══════════════════════════════════════════════════════════════════════════════
# 3. Blocklist — English, Telugu, Hindi
# ══════════════════════════════════════════════════════════════════════════════

class TestBlocklist:
    # --- English ---
    def test_english_caste_term_blocked(self):
        blocked, reason = check_blocked("interests", "I am a brahmin")
        assert blocked is True
        assert reason == "caste_community"

    def test_english_religion_term_blocked(self):
        blocked, reason = check_blocked("interests", "I am a Hindu")
        assert blocked is True
        assert reason == "religion"

    def test_english_address_blocked(self):
        blocked, reason = check_blocked("location_block", "door no 42 main street")
        assert blocked is True
        assert reason == "address"

    def test_aadhaar_12_digit_blocked(self):
        blocked, reason = check_blocked("current_or_past_work", "my id is 1234 5678 9012")
        assert blocked is True
        assert reason == "id_number"

    def test_phone_number_blocked(self):
        blocked, reason = check_blocked("current_or_past_work", "call me on 9876543210")
        assert blocked is True
        assert reason == "id_number"

    # --- Telugu ---
    def test_telugu_caste_blocked(self):
        # కులం = caste in Telugu
        blocked, reason = check_blocked("interests", "మా కులం రెడ్డి")
        assert blocked is True
        assert reason == "caste_community"

    def test_telugu_religion_blocked(self):
        # మతం = religion in Telugu
        blocked, reason = check_blocked("interests", "మా మతం హిందూ")
        assert blocked is True
        assert reason == "religion"

    def test_telugu_dalit_blocked(self):
        blocked, reason = check_blocked("interests", "మా జాతి దళిత")
        assert blocked is True
        assert reason == "caste_community"

    # --- Hindi ---
    def test_hindi_caste_blocked(self):
        # जाति = caste in Hindi
        blocked, reason = check_blocked("interests", "हमारी जाति यादव है")
        assert blocked is True
        assert reason == "caste_community"

    def test_hindi_religion_blocked(self):
        blocked, reason = check_blocked("interests", "हम हिंदू हैं")
        assert blocked is True
        assert reason == "religion"

    def test_hindi_address_blocked(self):
        blocked, reason = check_blocked("location_block", "हमारा पता गली नंबर 5 है")
        assert blocked is True
        assert reason == "address"

    # --- Clean text passes ---
    def test_clean_english_passes(self):
        blocked, _ = check_blocked("interests", "I am interested in tailoring")
        assert blocked is False

    def test_clean_telugu_passes(self):
        blocked, _ = check_blocked("interests", "నేను కుట్టుపని నేర్చుకోవాలనుకుంటున్నాను")
        assert blocked is False

    def test_clean_hindi_passes(self):
        blocked, _ = check_blocked("interests", "मुझे सिलाई सीखनी है")
        assert blocked is False

    def test_empty_string_passes(self):
        blocked, _ = check_blocked("skills", "")
        assert blocked is False


# ══════════════════════════════════════════════════════════════════════════════
# 4. Normalizer integration in update_profile
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizerIntegration:
    def test_telugu_interest_normalised_to_tailoring(self):
        sess = new_session()
        r = handle_update_profile({"interests": ["కుట్టుపని"]}, sess)
        assert r.get("ok") is True
        interests = sess.profile.get("interests", [])
        assert interests == ["tailoring"]

    def test_hindi_interest_silai_normalised(self):
        sess = new_session()
        r = handle_update_profile({"interests": ["सिलाई"]}, sess)
        assert r.get("ok") is True
        interests = sess.profile.get("interests", [])
        assert interests == ["tailoring"]

    def test_english_interest_tailoring_normalised(self):
        sess = new_session()
        r = handle_update_profile({"interests": ["tailoring"]}, sess)
        assert r.get("ok") is True
        interests = sess.profile.get("interests", [])
        assert interests == ["tailoring"]

    def test_english_skill_sewing_normalised(self):
        sess = new_session()
        r = handle_update_profile({"skills": ["sewing machine operator"]}, sess)
        assert r.get("ok") is True
        skills = sess.profile.get("skills", [])
        assert skills == ["sewing"]

    def test_telugu_skill_sewing_normalised(self):
        sess = new_session()
        r = handle_update_profile({"skills": ["కుట్టుపని"]}, sess)
        assert r.get("ok") is True
        skills = sess.profile.get("skills", [])
        assert skills == ["sewing"]

    def test_unknown_term_stored_as_free_text(self):
        sess = new_session()
        r = handle_update_profile({"interests": ["quantum_weaving"]}, sess)
        assert r.get("ok") is True
        interests = sess.profile.get("interests", [])
        assert "quantum_weaving" in interests

    def test_blocked_term_in_interests_dropped(self):
        sess = new_session()
        r = handle_update_profile({"interests": ["tailoring", "brahmin work"]}, sess)
        assert r.get("ok") is True
        interests = sess.profile.get("interests", [])
        assert interests == ["tailoring"]
        joined = " ".join(str(i) for i in interests).lower()
        assert "brahmin" not in joined

    def test_telugu_mobility_normalised(self):
        sess = new_session()
        r = handle_update_profile({"mobility": "ఇంటి వద్దే"}, sess)
        assert r.get("ok") is True
        assert sess.profile.get("mobility") == "home_only"

    def test_hindi_mobility_normalised(self):
        sess = new_session()
        r = handle_update_profile({"mobility": "घर पर"}, sess)
        assert r.get("ok") is True
        assert sess.profile.get("mobility") == "home_only"

    def test_current_work_normalised_to_trade(self):
        sess = new_session()
        r = handle_update_profile({"current_or_past_work": "silai"}, sess)
        assert r.get("ok") is True
        assert sess.profile.get("current_or_past_work") == "tailoring"


# ══════════════════════════════════════════════════════════════════════════════
# 5. Idempotency — latest value wins, history kept
# ══════════════════════════════════════════════════════════════════════════════

class TestIdempotency:
    def test_same_value_is_noop(self):
        sess = new_session()
        handle_update_profile({"education_level": "10th"}, sess)
        before_count = len(sess.field_history)
        handle_update_profile({"education_level": "10th"}, sess)
        assert len(sess.field_history) == before_count

    def test_latest_value_wins(self):
        sess = new_session()
        handle_update_profile({"education_level": "8th"}, sess)
        handle_update_profile({"education_level": "10th"}, sess)
        assert sess.profile["education_level"] == "10th"

    def test_history_tracks_all_changes(self):
        sess = new_session()
        handle_update_profile({"mobility": "home_only"}, sess)
        handle_update_profile({"mobility": "within_block"}, sess)
        mobility_history = [e for e in sess.field_history if e["field"] == "mobility"]
        assert len(mobility_history) == 2
        assert mobility_history[0]["new"] == "home_only"
        assert mobility_history[1]["new"] == "within_block"
        assert mobility_history[1]["old"] == "home_only"

    def test_interests_list_merged_not_replaced(self):
        sess = new_session()
        handle_update_profile({"interests": ["tailoring"]}, sess)
        handle_update_profile({"interests": ["catering"]}, sess)
        interests = sess.profile.get("interests", [])
        assert interests == ["tailoring", "catering"]

    def test_rate_limit_triggers_after_burst(self):
        """Sending > 5 updates within 1 second should trigger rate limiting."""
        sess = new_session()
        results = []
        for i in range(7):
            r = handle_update_profile({"max_training_months": i + 1}, sess)
            results.append(r)
        # At least one result should be rate_limited
        rate_limited = [r for r in results if r.get("error") == "rate_limited"]
        assert len(rate_limited) > 0


# ══════════════════════════════════════════════════════════════════════════════
# 6. confirm_profile validation
# ══════════════════════════════════════════════════════════════════════════════

class TestConfirmProfile:
    def test_missing_summary_rejected(self):
        sess = new_session()
        handle_update_profile({"education_level": "10th"}, sess)
        r = handle_confirm_profile({}, sess)
        assert r.get("error") == "missing_required"
        assert r.get("field") == "summary_spoken"

    def test_empty_profile_rejected(self):
        sess = new_session()
        r = handle_confirm_profile({"summary_spoken": "You have 10th pass."}, sess)
        assert r.get("error") == "empty_profile"

    def test_valid_confirm_sets_flag(self):
        sess = new_session()
        handle_update_profile({"education_level": "10th", "interests": ["tailoring"]}, sess)
        r = handle_confirm_profile(
            {"summary_spoken": "You passed 10th and want to learn tailoring."}, sess
        )
        assert r.get("ok") is True
        assert r.get("confirmed") is True
        assert sess.confirmed is True

    def test_missing_priority_fields_reported(self):
        sess = new_session()
        # Only set education_level — mobility etc. still missing
        handle_update_profile({"education_level": "10th"}, sess)
        r = handle_confirm_profile(
            {"summary_spoken": "You passed 10th."}, sess
        )
        assert r.get("ok") is True
        missing = r.get("missing_priority_fields", [])
        assert "mobility" in missing
        assert "interests" in missing


# ══════════════════════════════════════════════════════════════════════════════
# 7. Transcripts NEVER persisted — DB rule
# ══════════════════════════════════════════════════════════════════════════════

class TestTranscriptNotPersisted:
    def test_sessions_table_transcript_json_is_null(self):
        """The transcript_json column in DB must always be NULL."""
        from backend.db import get_db_connection, DB_PATH
        if not DB_PATH.exists():
            pytest.skip("Database not initialized")
        conn = get_db_connection()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT transcript_json FROM sessions WHERE transcript_json IS NOT NULL"
        ).fetchall()
        conn.close()
        assert len(rows) == 0, (
            f"Found {len(rows)} session(s) with non-NULL transcript_json – "
            "transcripts must never be persisted!"
        )

    def test_session_store_has_no_transcript_attr(self):
        """SessionState must not have a transcript field."""
        sess = create_session()
        assert not hasattr(sess, "transcript"), (
            "SessionState must not have a 'transcript' attribute"
        )
        assert not hasattr(sess, "transcript_json"), (
            "SessionState must not have a 'transcript_json' attribute"
        )

    def test_profile_export_contains_no_transcript_key(self):
        """to_profile_json() must not contain any 'transcript' key."""
        sess = create_session()
        handle_update_profile({"education_level": "10th"}, sess)
        profile_str = sess.to_profile_json()
        profile_data = json.loads(profile_str)
        for key in profile_data:
            assert "transcript" not in key.lower(), (
                f"Transcript data found under key '{key}' in profile JSON"
            )


# ══════════════════════════════════════════════════════════════════════════════
# 8. Tool declaration wiring & Persona A integration
# ══════════════════════════════════════════════════════════════════════════════

class TestToolDeclarationWiring:
    def test_update_profile_declaration_has_non_blocking_behavior(self):
        from google.genai import types
        from backend.live import _make_function_declaration
        from backend.tools import UPDATE_PROFILE_DECLARATION
        fd = _make_function_declaration(UPDATE_PROFILE_DECLARATION)
        assert fd.behavior == types.Behavior.NON_BLOCKING

    def test_confirm_profile_declaration_has_blocking_behavior(self):
        from google.genai import types
        from backend.live import _make_function_declaration
        from backend.tools import CONFIRM_PROFILE_DECLARATION
        fd = _make_function_declaration(CONFIRM_PROFILE_DECLARATION)
        assert fd.behavior == types.Behavior.BLOCKING

    def test_ping_declaration_has_non_blocking_behavior(self):
        from google.genai import types
        from backend.live import _make_function_declaration
        from backend.tools import PING_DECLARATION
        fd = _make_function_declaration(PING_DECLARATION)
        assert fd.behavior == types.Behavior.NON_BLOCKING

    def test_update_profile_response_scheduling_is_silent(self):
        from google.genai import types
        resp = types.FunctionResponse(
            name="update_profile",
            id="call_1",
            response={"ok": True},
            scheduling=types.FunctionResponseScheduling.SILENT,
        )
        assert resp.scheduling == types.FunctionResponseScheduling.SILENT


class TestPersonaAEndToEnd:
    def test_persona_a_through_tools_produces_tailoring_first(self):
        from backend.schema import ProfileSchema
        from backend.engine import compute_pathways
        sess = create_session(language="te")
        r = handle_update_profile({
            "education_level": "10th",
            "interests": ["tailoring"],
            "skills": ["sewing"],
            "assets": ["sewing machine"],
            "mobility": "home_only",
            "work_preference": "self",
        }, sess)
        assert r.get("ok") is True
        assert sess.profile.get("interests") == ["tailoring"]
        assert sess.profile.get("skills") == ["sewing"]
        assert sess.profile.get("assets") == ["sewing machine"]

        profile_obj = ProfileSchema(**sess.profile)
        res = compute_pathways(profile_obj)
        assert len(res.pathways) > 0
        top = res.pathways[0]
        assert top.trade == "tailoring"

