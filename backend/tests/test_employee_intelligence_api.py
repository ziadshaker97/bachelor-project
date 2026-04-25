from fastapi.testclient import TestClient

from app.main import app


def test_historical_employee_profile_includes_cv_and_training_months() -> None:
    with TestClient(app) as client:
        response = client.get("/profiles/emp-demo-005")
        assert response.status_code == 200
        payload = response.json()
        assert payload["profile"]["employee_id"] == "emp-demo-005"
        assert payload["profile"]["months_in_training"] == 6
        assert payload["profile"]["cv_summary"]


def test_employee_intelligence_endpoint_returns_next_steps() -> None:
    with TestClient(app) as client:
        response = client.get("/employee-intelligence/emp-demo-005")
        assert response.status_code == 200
        payload = response.json()
        assert payload["employee_id"] == "emp-demo-005"
        assert payload["ai_message"]
        assert payload["next_steps"]
        assert payload["recommended_module_ids"]
