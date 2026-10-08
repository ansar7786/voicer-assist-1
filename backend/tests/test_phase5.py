"""
Tests for Phase 5: Live pathways and what-if simulation (FR-15 to FR-17, FR-35, FR-36).
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.session_store import SessionState
from backend.live import get_tool_behavior
from backend.tools import (
    GET_PATHWAYS_DECLARATION,
    SET_CONSTRAINT_DECLARATION,
    handle_get_pathways,
    handle_set_constraint,
)

client = TestClient(app)


def test_tool_declarations_blocking():
    """Verify Phase 5 tool declarations are BLOCKING as required by PRD."""
    assert GET_PATHWAYS_DECLARATION["behavior"] == "BLOCKING"
    assert SET_CONSTRAINT_DECLARATION["behavior"] == "BLOCKING"
    assert get_tool_behavior("get_pathways") == "BLOCKING"
    assert get_tool_behavior("set_constraint") == "BLOCKING"


def test_get_pathways_unconfirmed_preview():
    """get_pathways before confirmation returns an unconfirmed preview marker."""
    session = SessionState(session_id="test_p5_unconfirmed")
    session.profile = {
        "education_level": "10th",
        "skills": ["tailoring"],
        "interests": ["tailoring"],
        "max_training_months": 6,
    }
    session.confirmed = False

    res = handle_get_pathways({}, session)

    assert res["unconfirmed"] is True
    assert "UNCONFIRMED PREVIEW" in res["text"]
    assert "score" not in res["text"].lower()
    assert len(res["pathways"]) > 0
    assert len(session.previous_pathways) > 0


def test_get_pathways_confirmed():
    """get_pathways after confirmation returns confirmed pathways without preview marker."""
    session = SessionState(session_id="test_p5_confirmed")
    session.profile = {
        "education_level": "10th",
        "skills": ["tailoring"],
        "interests": ["tailoring"],
        "max_training_months": 6,
    }
    session.confirmed = True

    res = handle_get_pathways({}, session)

    assert res["unconfirmed"] is False
    assert "UNCONFIRMED PREVIEW" not in res["text"]
    assert "score" not in res["text"].lower()
    assert len(res["pathways"]) > 0
    # Opportunity status check
    for p in res["pathways"]:
        opp_status = p.get("opportunity_status")
        assert opp_status is not None


def test_set_constraint_diff_and_no_scores():
    """set_constraint produces short structured diff summary with no numeric scores."""
    session = SessionState(session_id="test_p5_constraint")
    session.profile = {
        "education_level": "10th",
        "skills": ["tailoring", "embroidery"],
        "interests": ["tailoring"],
        "max_training_months": 12,
    }
    session.confirmed = True

    # Initial compute
    init_res = handle_get_pathways({}, session)
    assert len(init_res["pathways"]) > 0

    # Constrain to 1 month
    res = handle_set_constraint(
        {"max_training_months": 1},
        session,
    )

    assert "diff" in res
    assert "added" in res["diff"]
    assert "removed" in res["diff"]
    assert "kept" in res["diff"]
    assert "score" not in res["text"].lower()
    # Check that diff text mentions changes
    assert ("Dropped" in res["text"] or "Kept" in res["text"] or "Added" in res["text"])


def test_set_constraint_validation():
    """Invalid constraints return recoverable tool error responses."""
    session = SessionState(session_id="test_p5_val")
    session.profile = {"skills": ["tailoring"]}

    # Invalid months (> 12)
    res_err1 = handle_set_constraint({"max_training_months": 18}, session)
    assert res_err1.get("error") == "invalid_value"
    assert "between 1 and 12" in res_err1["text"]

    # Invalid mobility enum
    res_err2 = handle_set_constraint({"mobility": "outer_space"}, session)
    assert res_err2.get("error") == "invalid_value"
    assert "Invalid mobility" in res_err2["text"]


def test_set_constraint_reset():
    """reset=True clears constraints and restores pathways."""
    session = SessionState(session_id="test_p5_reset")
    session.profile = {
        "education_level": "10th",
        "skills": ["tailoring"],
        "interests": ["tailoring"],
        "max_training_months": 6,
    }
    handle_get_pathways({}, session)

    # Set restrictive constraint
    handle_set_constraint({"max_training_months": 1}, session)
    assert session.constraints.get("max_training_months") == 1

    # Reset
    res_reset = handle_set_constraint({"reset": True}, session)
    assert "Reset all simulated constraints" in res_reset["text"]
    assert session.constraints.get("max_training_months") is None


def test_explain_endpoint_fallback():
    """POST /api/explain returns fallback explanation when LLM is unavailable."""
    payload = {
        "reasons": [
            "Matches candidate tailoring skills",
            "Available in local block within 3 months",
        ],
        "language": "en",
    }
    resp = client.post("/api/explain", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "explanation" in data
    assert len(data["explanation"]) > 0
    # Must contain the factual reasons or derived plain explanation
    assert "tailoring" in data["explanation"].lower() or "matches" in data["explanation"].lower()


def test_explain_endpoint_with_factors():
    """POST /api/explain accepts factor objects and extracts reasons."""
    payload = {
        "factors": [
            {"factor": "skill_match", "label": "High", "reason": "Demonstrated hand-embroidery skills"},
            {"factor": "centre_proximity", "label": "High", "reason": "Training centre within 5km"},
        ],
        "language": "en",
    }
    resp = client.post("/api/explain", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "explanation" in data
    assert "hand-embroidery" in data["explanation"] or "training centre" in data["explanation"].lower()
