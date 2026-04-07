from app.db import init_db, save_profile
from app.models import EmployeeProfile
from app.services.chat import ChatService


def test_chat_returns_grounded_sources() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-10",
        role="Software Engineer",
        department="Platform",
        experience_level="beginner",
        known_skills=["security awareness"],
        learning_preferences=["video"],
    )
    save_profile(profile)

    service = ChatService()
    response = service.reply("session-a", profile, "How do I request tool access?")
    assert response.sources
    assert response.answer


def test_unsupported_question_avoids_specific_policy_claims() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-11",
        role="Data Analyst",
        department="Analytics",
        experience_level="intermediate",
        known_skills=["sql"],
        learning_preferences=["text"],
    )
    save_profile(profile)

    service = ChatService()
    response = service.reply("session-b", profile, "What is our office mascot's favorite food?")
    assert "grounded" in response.answer.lower() or "could not find" in response.answer.lower()


def test_follow_up_uses_history_without_failing() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-12",
        role="Product Manager",
        department="Product",
        experience_level="intermediate",
        known_skills=["communication"],
        learning_preferences=["workshop"],
    )
    save_profile(profile)

    service = ChatService()
    first = service.reply("session-c", profile, "How do I request leave?")
    second = service.reply("session-c", profile, "Who approves it?")
    assert first.answer
    assert second.answer
    assert second.sources
    assert any("leave" in item.snippet.lower() or "manager" in item.snippet.lower() for item in second.sources)
    assert "could not find" not in second.answer.lower()
