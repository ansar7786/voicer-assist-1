"""
Integration tests for POST /api/pathways and POST /api/recompute endpoints.
"""
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_api_pathways_persona_a():
    payload = {
        "profile": {
            "education_level": "10th",
            "skills": ["sewing"],
            "assets": ["sewing machine"],
            "interests": ["tailoring"],
            "mobility": "home_only",
            "work_preference": "self",
        },
        "constraints": None,
    }
    response = client.post("/api/pathways", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "pathways" in data
    assert "excluded" in data
    assert len(data["pathways"]) > 0
    top = data["pathways"][0]
    assert top["trade"] == "tailoring"
    # Verify NO numeric scores in output
    assert "score" not in top
    assert "composite_score" not in top
    assert "numeric_score" not in top

def test_api_recompute_with_diff():
    # Initial pathways request
    initial_payload = {
        "profile": {
            "education_level": "10th",
            "interests": ["tailoring", "catering"],
            "work_preference": "either",
        },
        "constraints": None,
    }
    init_res = client.post("/api/pathways", json=initial_payload)
    assert init_res.status_code == 200
    init_pathways = init_res.json()["pathways"]
    previous_ids = [p["id"] for p in init_pathways]

    # Recompute with constraint: max 2 months and home_only
    recompute_payload = {
        "profile": {
            "education_level": "10th",
            "interests": ["tailoring", "catering"],
            "work_preference": "either",
        },
        "previous_pathway_ids": previous_ids,
        "constraints": {
            "max_training_months": 2,
            "mobility": "home_only",
        },
    }
    recomp_res = client.post("/api/recompute", json=recompute_payload)
    assert recomp_res.status_code == 200
    recomp_data = recomp_res.json()
    assert "diff" in recomp_data
    diff = recomp_data["diff"]
    assert "added" in diff
    assert "removed" in diff
    assert "kept" in diff
    # Verify removed pathways have human-readable reasons
    for rem in diff["removed"]:
        assert len(rem["reason"]) > 0
