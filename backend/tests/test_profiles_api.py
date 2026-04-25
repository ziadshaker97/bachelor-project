from fastapi.testclient import TestClient

from app.main import app


def test_seeded_employee_profile_can_be_loaded_by_id() -> None:
    with TestClient(app) as client:
        response = client.get("/profiles/emp-demo-001")
        assert response.status_code == 200
        payload = response.json()
        assert payload["profile"]["employee_id"] == "emp-demo-001"
        assert payload["profile"]["department"] == "Platform"
        assert payload["profile"]["role"] == "Software Engineer"


def test_admin_profile_can_be_loaded_by_id() -> None:
    with TestClient(app) as client:
        response = client.get("/profiles/admin-demo-001")
        assert response.status_code == 200
        payload = response.json()
        assert payload["profile"]["employee_id"] == "admin-demo-001"
        assert payload["profile"]["access_level"] == "admin"
