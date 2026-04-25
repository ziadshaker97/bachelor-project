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


def test_new_short_question_is_not_forced_into_previous_topic() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-12b",
        role="Software Engineer",
        department="Platform",
        experience_level="beginner",
        known_skills=["git"],
        learning_preferences=["video"],
    )
    save_profile(profile)

    service = ChatService()
    service.reply("session-c2", profile, "How do I request leave?")
    second = service.reply("session-c2", profile, "What are the working hours?")
    assert "leave requests are submitted through the hr portal" not in second.answer.lower()
    assert "grounded onboarding guidance" in second.answer.lower() or "could not find" in second.answer.lower()


def test_course_question_returns_real_courses() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-13",
        role="Software Engineer",
        department="Platform",
        experience_level="beginner",
        known_skills=["python"],
        learning_preferences=["interactive"],
    )
    save_profile(profile)

    service = ChatService()
    response = service.reply("session-d", profile, "What courses should I take to improve my Python and Git skills?")
    assert response.answer
    assert response.recommended_courses
    assert any("python" in course.title.lower() or "git" in course.title.lower() for course in response.recommended_courses)


def test_javascript_course_question_prefers_javascript_matches() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-14",
        role="Software Engineer",
        department="Platform",
        experience_level="beginner",
        known_skills=["git"],
        learning_preferences=["interactive"],
    )
    save_profile(profile)

    service = ChatService()
    response = service.reply("session-e", profile, "Show me JavaScript courses for front-end work")
    assert response.recommended_courses
    assert any("javascript" in course.title.lower() or "react" in course.title.lower() for course in response.recommended_courses)


def test_cross_department_course_query_can_reach_requested_topic() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-15",
        role="Data Analyst",
        department="Analytics",
        experience_level="intermediate",
        known_skills=["sql"],
        learning_preferences=["text"],
    )
    save_profile(profile)

    service = ChatService()
    response = service.reply("session-f", profile, "I want Java courses")
    assert response.recommended_courses
    assert any("java" in course.title.lower() for course in response.recommended_courses)


def test_power_bi_query_returns_power_bi_course() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-16",
        role="Software Engineer",
        department="Platform",
        experience_level="intermediate",
        known_skills=["git"],
        learning_preferences=["video"],
    )
    save_profile(profile)

    service = ChatService()
    response = service.reply("session-g", profile, "Show me Power BI courses")
    assert response.recommended_courses
    assert any("power bi" in course.title.lower() for course in response.recommended_courses)


def test_unknown_topic_returns_internal_learning_path() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-17",
        role="Data Analyst",
        department="Analytics",
        experience_level="intermediate",
        known_skills=["sql"],
        learning_preferences=["video"],
    )
    save_profile(profile)

    service = ChatService()
    response = service.reply("session-h", profile, "Show me Tableau courses")
    assert response.recommended_courses
    assert all("tableau" in course.title.lower() for course in response.recommended_courses)
    assert all(course.delivery_mode == "internal" for course in response.recommended_courses)
    assert all(course.syllabus for course in response.recommended_courses)


def test_short_next_step_questions_route_to_progress_engine() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-18",
        role="Data Analyst",
        department="Analytics",
        experience_level="intermediate",
        known_skills=["sql", "excel"],
        learning_preferences=["text"],
    )
    save_profile(profile)

    service = ChatService()
    response = service.reply("session-i", profile, "what to do next")
    assert "could not find grounded onboarding guidance" not in response.answer.lower()
    assert response.recommended_module_ids


def test_short_module_next_question_routes_to_progress_engine() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-19",
        role="Data Analyst",
        department="Analytics",
        experience_level="intermediate",
        known_skills=["sql", "excel"],
        learning_preferences=["text"],
    )
    save_profile(profile)

    service = ChatService()
    response = service.reply("session-j", profile, "what module to do next")
    assert "could not find grounded onboarding guidance" not in response.answer.lower()
    assert response.recommended_module_ids


def test_next_modules_to_start_routes_to_progress_engine() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-20",
        role="Data Analyst",
        department="Analytics",
        experience_level="intermediate",
        known_skills=["sql", "excel"],
        learning_preferences=["text"],
    )
    save_profile(profile)

    service = ChatService()
    response = service.reply("session-k", profile, "i mean next modules to start")
    assert "could not find grounded onboarding guidance" not in response.answer.lower()
    assert response.recommended_module_ids


def test_ambiguous_follow_up_uses_progress_fallback() -> None:
    init_db()
    profile = EmployeeProfile(
        employee_id="emp-21",
        role="Data Analyst",
        department="Analytics",
        experience_level="intermediate",
        known_skills=["sql", "excel"],
        learning_preferences=["text"],
    )
    save_profile(profile)

    service = ChatService()
    service.reply("session-l", profile, "What module should I start next?")
    response = service.reply("session-l", profile, "what next")
    assert "could not find grounded onboarding guidance" not in response.answer.lower()
    assert response.recommended_module_ids
