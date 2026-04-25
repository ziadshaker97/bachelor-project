from __future__ import annotations

import re
from difflib import get_close_matches

from ..models import EmployeeInsightResponse, EmployeeProfile, RecommendationAction
from ..seed import load_courses, load_modules
from .modules import ModuleProgressService
from .progress import ProgressService
from .recommendation import RecommendationService


TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")
INTELLIGENCE_VOCAB = {
    "progress",
    "track",
    "tracking",
    "next",
    "after",
    "then",
    "do",
    "start",
    "step",
    "steps",
    "module",
    "modules",
    "recommend",
    "recommendation",
    "recommendations",
    "improve",
    "focus",
    "plan",
    "roadmap",
    "doing",
    "growth",
    "skill",
    "skills",
    "training",
    "complete",
    "completed",
    "finish",
    "finished",
    "done",
}
DEPARTMENT_SKILL_MAP = {
    "platform": ["python", "git", "debugging", "automation", "backend", "security awareness"],
    "analytics": ["sql", "power bi", "reporting", "data visualization", "analysis", "governance"],
    "product": ["roadmapping", "stakeholder management", "communication", "workflow"],
    "operations": ["workflow", "process mapping", "reporting", "communication"],
}


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


class EmployeeIntelligenceService:
    def __init__(self) -> None:
        self.progress = ProgressService()
        self.module_progress = ModuleProgressService()
        self.recommender = RecommendationService()
        self.courses = load_courses()
        self.modules = {module.module_id: module for module in load_modules()}

    @staticmethod
    def _normalized_message_tokens(message: str) -> set[str]:
        normalized: set[str] = set()
        for token in _tokens(message):
            normalized.add(token)
            fuzzy = get_close_matches(token, INTELLIGENCE_VOCAB, n=1, cutoff=0.8)
            if fuzzy:
                normalized.add(fuzzy[0])
        return normalized

    def _known_skill_set(self, profile: EmployeeProfile, progress_course_ids: set[str]) -> set[str]:
        skill_set = {skill.lower() for skill in profile.known_skills}
        skill_set |= _tokens(profile.cv_summary)
        for course in self.courses:
            if course.course_id in progress_course_ids:
                skill_set |= {skill.lower() for skill in course.skills}
        return skill_set

    def _recommended_courses_for_gaps(self, profile: EmployeeProfile, completed_ids: set[str], gap_skills: list[str]) -> list:
        matches = []
        goal_tokens = set()
        for goal in profile.career_goals:
            goal_tokens |= _tokens(goal)
        for course in self.courses:
            if course.course_id in completed_ids:
                continue
            course_skills = {skill.lower() for skill in course.skills}
            course_tags = {tag.lower() for tag in course.tags}
            score = len(course_skills & set(gap_skills))
            score += len(course_skills & goal_tokens)
            if profile.role.lower() in course_tags or profile.department.lower() in course_tags:
                score += 1
            if "backend" in goal_tokens and "backend" in course_skills:
                score += 2
            if "automation" in goal_tokens and "automation" in course_skills:
                score += 2
            if score:
                matches.append((score, course))
        matches.sort(key=lambda item: item[0], reverse=True)
        return [course for _, course in matches[:3]]

    def _visible_module_ids(self, profile: EmployeeProfile) -> set[str]:
        return {
            module_id
            for module_id, module in self.modules.items()
            if self.recommender._is_module_relevant(profile, module)
        }

    def build(self, profile: EmployeeProfile) -> EmployeeInsightResponse:
        progress_rows = self.progress.list_progress(profile.employee_id)
        module_progress_rows = self.module_progress.list_progress(profile.employee_id)
        visible_module_ids = self._visible_module_ids(profile)
        completed_ids = {item.course_id for item in progress_rows if item.status == "completed"}
        active_ids = {item.course_id for item in progress_rows if item.status == "in_progress"}
        all_progress_ids = completed_ids | active_ids
        completed_module_ids = {
            item.module_id
            for item in module_progress_rows
            if (item.status == "completed" or item.progress_percent >= 100) and item.module_id in visible_module_ids
        }
        active_module_ids = {
            item.module_id
            for item in module_progress_rows
            if item.status == "in_progress" and item.module_id in visible_module_ids
        }
        known_skill_set = self._known_skill_set(profile, progress_course_ids=all_progress_ids)

        target_skills = DEPARTMENT_SKILL_MAP.get(profile.department.lower(), profile.known_skills or ["communication"])
        strengths = [skill for skill in target_skills if skill.lower() in known_skill_set][:4]
        skill_gaps = [skill for skill in target_skills if skill.lower() not in known_skill_set][:4]

        recommendations = [
            item for item in self.recommender.recommend(profile, top_k=6)
            if item.module_id not in completed_module_ids
        ][:3]
        recommended_courses = self._recommended_courses_for_gaps(profile, completed_ids, skill_gaps)

        completed_count = len(completed_ids)
        active_count = len(active_ids)
        if profile.months_in_training >= 6 and completed_count >= 3:
            progress_stage = "advanced momentum"
        elif completed_count or active_count:
            progress_stage = "on track"
        else:
            progress_stage = "early setup"

        next_steps: list[RecommendationAction] = []
        if active_module_ids:
            active_module = self.modules.get(next(iter(active_module_ids)))
            if active_module:
                next_steps.append(
                    RecommendationAction(
                        title="Continue your active internal module",
                        detail=f"Return to {active_module.title} and finish its remaining sections before starting another internal module.",
                        action_type="module",
                    )
                )
        elif recommendations:
            lead_module = self.modules.get(recommendations[0].module_id)
            next_steps.append(
                RecommendationAction(
                    title="Complete your next internal module",
                    detail=f"Focus on {(lead_module.title if lead_module else recommendations[0].module_id)} because it is aligned with your {profile.role} responsibilities and current learning path.",
                    action_type="module",
                )
            )
        if recommended_courses:
            next_steps.append(
                RecommendationAction(
                    title="Advance a skill gap",
                    detail=f"Open {recommended_courses[0].title} to strengthen {', '.join(recommended_courses[0].skills[:2])}.",
                    action_type="course",
                )
            )
        if skill_gaps:
            next_steps.append(
                RecommendationAction(
                    title="Apply a skill in your work",
                    detail=f"Ask your manager for a task that helps you practice {skill_gaps[0]} in real team work this week.",
                    action_type="practice",
                )
            )

        strengths_text = ", ".join(strengths[:2]) if strengths else "core onboarding foundations"
        gap_text = ", ".join(skill_gaps[:2]) if skill_gaps else "deeper role ownership"
        if profile.months_in_training >= 6:
            ai_message = (
                f"You have {profile.months_in_training} months of training history, solid momentum in {strengths_text}, "
                f"and the next growth area is {gap_text}. Based on your department and completed work, you are ready for more advanced responsibilities."
            )
        else:
            ai_message = (
                f"Your current onboarding progress shows strength in {strengths_text}. "
                f"The AI engine recommends focusing next on {gap_text} so your learning plan stays aligned with your {profile.department} work."
            )

        return EmployeeInsightResponse(
            employee_id=profile.employee_id,
            progress_stage=progress_stage,
            ai_message=ai_message,
            strengths=strengths,
            skill_gaps=skill_gaps,
            next_steps=next_steps,
            recommended_module_ids=[item.module_id for item in recommendations],
            recommended_courses=recommended_courses,
        )

    def is_progress_query(self, message: str) -> bool:
        lowered = message.lower()
        if any(
            phrase in lowered
            for phrase in (
                "what should i do now",
                "what should i do next",
                "what do i do next",
                "what to do next",
                "what module to do next",
                "which module next",
                "which module should i do next",
                "next modules to start",
                "next module to start",
                "what modules should i start next",
                "what module should i start next",
                "what should i do after this",
                "what now",
                "now what",
                "what is my next step",
                "tell me my next step",
                "tell me the next step",
                "what should be my next",
                "how am i doing",
                "track my progress",
                "recommend for me",
                "give me recommendations",
            )
        ):
            return True

        normalized_tokens = self._normalized_message_tokens(message)
        score = 0
        if "progress" in normalized_tokens or "track" in normalized_tokens:
            score += 2
        if "recommend" in normalized_tokens or "recommendations" in normalized_tokens:
            score += 2
        if "next" in normalized_tokens and ("step" in normalized_tokens or "steps" in normalized_tokens):
            score += 3
        if "next" in normalized_tokens and "module" in normalized_tokens:
            score += 3
        if "next" in normalized_tokens and "modules" in normalized_tokens:
            score += 3
        if "next" in normalized_tokens and "do" in normalized_tokens:
            score += 2
        if ("module" in normalized_tokens or "modules" in normalized_tokens) and "start" in normalized_tokens:
            score += 3
        if "after" in normalized_tokens and ("module" in normalized_tokens or "training" in normalized_tokens):
            score += 2
        if "focus" in normalized_tokens or "improve" in normalized_tokens or "growth" in normalized_tokens:
            score += 1
        if "module" in normalized_tokens or "modules" in normalized_tokens:
            score += 1
        if "skill" in normalized_tokens or "skills" in normalized_tokens:
            score += 1
        if "training" in normalized_tokens or "plan" in normalized_tokens or "roadmap" in normalized_tokens:
            score += 1
        if "doing" in normalized_tokens:
            score += 1
        return score >= 3

    def chat_answer(self, profile: EmployeeProfile, message: str) -> tuple[str, list[str], list]:
        insight = self.build(profile)
        answer = insight.ai_message
        if insight.next_steps:
            answer += f" Next, {insight.next_steps[0].detail}"
        lowered = message.lower()
        should_include_courses = any(keyword in lowered for keyword in ("course", "courses", "learn", "learning", "class", "classes"))
        return answer, insight.recommended_module_ids, (insight.recommended_courses if should_include_courses else [])

    def should_fallback_to_progress(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        has_sources: bool = False,
        has_courses: bool = False,
    ) -> bool:
        if self.is_progress_query(message):
            return True
        if has_sources or has_courses:
            return False

        normalized_tokens = self._normalized_message_tokens(message)
        history = history or []
        recent_text = " ".join(item.get("message", "") for item in history[-4:]).lower()
        recent_tokens = self._normalized_message_tokens(recent_text)

        planning_tokens = {
            "next", "after", "then", "module", "modules", "training", "plan",
            "progress", "recommend", "recommendations", "start", "complete",
            "completed", "finish", "finished", "done", "step", "steps", "focus",
        }
        overlap = len(normalized_tokens & planning_tokens)
        contextual_overlap = len((normalized_tokens | recent_tokens) & planning_tokens)

        short_message = len(_tokens(message)) <= 8
        asks_for_what_next = "what" in normalized_tokens and ("next" in normalized_tokens or "after" in normalized_tokens)
        mentions_modules = "module" in normalized_tokens or "modules" in normalized_tokens
        mentions_completion = any(token in normalized_tokens for token in {"complete", "completed", "finish", "finished", "done"})

        return (
            overlap >= 2
            or (short_message and asks_for_what_next)
            or (short_message and mentions_modules)
            or (mentions_completion and contextual_overlap >= 2)
            or (short_message and contextual_overlap >= 3)
        )
