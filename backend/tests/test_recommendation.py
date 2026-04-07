from app.models import EmployeeProfile
from app.services.recommendation import RecommendationService


def test_role_and_skill_gap_drive_recommendations() -> None:
    service = RecommendationService()
    profile = EmployeeProfile(
        employee_id="emp-1",
        role="Software Engineer",
        department="Platform",
        experience_level="intermediate",
        known_skills=["python"],
        learning_preferences=["interactive", "video"],
    )

    results = service.recommend(profile, top_k=3)
    top_ids = [item.module_id for item in results]
    assert "mod-eng-stack" in top_ids
    eng_stack = next(item for item in results if item.module_id == "mod-eng-stack")
    assert eng_stack.reason_codes


def test_cold_start_profile_still_gets_recommendations() -> None:
    service = RecommendationService()
    profile = EmployeeProfile(
        employee_id="emp-2",
        role="Operations Analyst",
        department="Operations",
        experience_level="beginner",
        known_skills=[],
        learning_preferences=[],
    )

    results = service.recommend(profile, top_k=5)
    assert len(results) == 5
    assert all(result.score >= 0 for result in results)


def test_explanation_fields_are_populated() -> None:
    service = RecommendationService()
    profile = EmployeeProfile(
        employee_id="emp-3",
        role="Product Manager",
        department="Product",
        experience_level="intermediate",
        known_skills=["communication"],
        learning_preferences=["workshop"],
    )

    results = service.recommend(profile, top_k=1)
    assert results[0].reason_codes
    assert results[0].reason_text


def test_recommend_with_strategy_returns_model_or_heuristic() -> None:
    service = RecommendationService()
    profile = EmployeeProfile(
        employee_id="emp-4",
        role="Data Analyst",
        department="Analytics",
        experience_level="intermediate",
        known_skills=["sql"],
        learning_preferences=["text"],
    )

    results, strategy = service.recommend_with_strategy(profile, top_k=2)
    assert strategy in {"model", "heuristic"}
    assert len(results) == 2
