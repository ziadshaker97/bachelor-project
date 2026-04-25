from fastapi.testclient import TestClient

from app.main import app


def test_progress_update_and_admin_summary() -> None:
    with TestClient(app) as client:
        update_response = client.post(
            "/progress",
            json={
                "employee_id": "emp-demo-001",
                "course_id": "course-se-001",
                "status": "in_progress",
                "progress_percent": 40,
                "saved_for_later": False,
            },
        )
        assert update_response.status_code == 200
        progress_payload = update_response.json()
        assert progress_payload["employee_id"] == "emp-demo-001"
        assert progress_payload["progress"][0]["course_id"] == "course-se-001"

        roadmap_response = client.get("/roadmap/emp-demo-001")
        assert roadmap_response.status_code == 200
        roadmap_payload = roadmap_response.json()
        assert roadmap_payload["role"] == "Software Engineer"
        assert roadmap_payload["milestones"]

        admin_response = client.get("/admin/summary")
        assert admin_response.status_code == 200
        admin_payload = admin_response.json()
        assert admin_payload["total_employees"] >= 4
        assert any(item["employee_id"] == "emp-demo-001" for item in admin_payload["employee_summaries"])
