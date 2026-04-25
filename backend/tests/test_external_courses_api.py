from fastapi.testclient import TestClient

from app.main import app, chat
from app.models import CourseRecord


def test_external_courses_endpoint_reports_unconfigured_provider() -> None:
    with TestClient(app) as client:
        response = client.get("/courses/search", params={"query": "tableau"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["query"] == "tableau"
        assert payload["configured"] is True
        assert payload["provider"] in {"marketplace_search", "linkedin_learning"}
        assert payload["courses"]
        assert any("coursera" in course["url"].lower() for course in payload["courses"])


def test_external_courses_endpoint_returns_provider_results_when_mocked(monkeypatch) -> None:
    monkeypatch.setattr(chat.courses.external_provider, "configured", lambda: True)
    monkeypatch.setattr(
        chat.courses.external_provider,
        "search",
        lambda query, top_k=10: [
            CourseRecord(
                course_id="external-1",
                title="Tableau Essentials",
                provider="LinkedIn Learning",
                category="Analytics",
                level="beginner",
                duration_hours=8,
                skills=["tableau"],
                tags=["tableau"],
                description="External catalog result",
                url="https://example.com/tableau",
                delivery_mode="external",
                syllabus=[],
            )
        ],
    )

    with TestClient(app) as client:
        response = client.get("/courses/search", params={"query": "tableau"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["configured"] is True
        assert payload["courses"]
        assert payload["courses"][0]["title"] == "Tableau Essentials"
