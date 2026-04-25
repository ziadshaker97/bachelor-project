import math
import re
from collections import Counter

import httpx

from ..models import CourseProgressRecord, CourseRecord, EmployeeProfile
from ..seed import load_courses
from .external_courses import NullExternalCourseProvider, build_external_course_provider


TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")
SLUG_RE = re.compile(r"[^a-z0-9]+")
ALIASES = {
    "js": "javascript",
    "reactjs": "react",
    "frontend": "front-end",
    "node": "nodejs",
    "powerbi": "power bi",
    "power-bi": "power bi",
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "about",
    "are",
    "for",
    "i",
    "me",
    "need",
    "of",
    "on",
    "or",
    "show",
    "tell",
    "the",
    "to",
    "what",
    "with",
}
COURSE_WORDS = {
    "bootcamp",
    "class",
    "classes",
    "course",
    "courses",
    "learn",
    "learning",
    "path",
    "paths",
    "program",
    "training",
    "trainings",
}

def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_RE.findall(text):
        lowered = token.lower()
        normalized = ALIASES.get(lowered, lowered)
        if normalized not in STOPWORDS:
            tokens.append(normalized)
    return tokens


class CourseCatalogService:
    def __init__(self) -> None:
        self.courses = load_courses()
        self.external_provider = build_external_course_provider()
        self.course_vectors = {
            course.course_id: self._course_vector(course)
            for course in self.courses
        }
        self.catalog_terms = {
            token
            for vector in self.course_vectors.values()
            for token in vector
        }

    @staticmethod
    def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
        keys = set(left) | set(right)
        dot = sum(left[key] * right[key] for key in keys)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    @staticmethod
    def _course_vector(course: CourseRecord) -> Counter[str]:
        vector: Counter[str] = Counter()
        vector.update(_tokens(course.title))
        vector.update(_tokens(course.description))
        vector.update(_tokens(" ".join(course.skills)))
        vector.update(_tokens(" ".join(course.tags)))
        vector.update(_tokens(f"{course.category} {course.level} {course.provider}"))
        return vector

    @staticmethod
    def _profile_context(profile: EmployeeProfile) -> list[str]:
        return [
            profile.role,
            profile.department,
            profile.experience_level,
            *profile.known_skills,
            *profile.learning_preferences,
        ]

    @staticmethod
    def _explicit_query_tokens(message: str) -> set[str]:
        return set(_tokens(message))

    @staticmethod
    def _ordered_topic_tokens(message: str) -> list[str]:
        topic_tokens: list[str] = []
        for token in _tokens(message):
            if token in COURSE_WORDS:
                continue
            if token not in topic_tokens:
                topic_tokens.append(token)
        return topic_tokens

    def _specific_query_tokens(self, message: str) -> set[str]:
        explicit = self._explicit_query_tokens(message)
        return {
            token for token in explicit
            if token in self.catalog_terms and token not in COURSE_WORDS
        }

    @staticmethod
    def _format_topic_label(topic_tokens: list[str]) -> str:
        if not topic_tokens:
            return "recommended"
        return " ".join(token.upper() if len(token) <= 3 else token.capitalize() for token in topic_tokens)

    @staticmethod
    def _slugify_topic(topic_label: str) -> str:
        slug = SLUG_RE.sub("-", topic_label.lower()).strip("-")
        return slug or "topic"

    def _build_internal_topic_courses(self, topic_tokens: list[str], top_k: int) -> list[CourseRecord]:
        if not topic_tokens:
            return []
        topic_label = self._format_topic_label(topic_tokens)
        slug = self._slugify_topic(topic_label)
        blueprints = (
            (
                "Foundations",
                "beginner",
                6,
                [
                    f"Introduction to {topic_label}",
                    f"Core concepts and terminology in {topic_label}",
                    f"Hands-on beginner exercises for {topic_label}",
                    f"Common use cases and onboarding checkpoints for {topic_label}",
                ],
            ),
            (
                "Applied Practice",
                "intermediate",
                10,
                [
                    f"Intermediate workflows in {topic_label}",
                    f"Applying {topic_label} in department scenarios",
                    f"Building a practical {topic_label} mini-project",
                    f"Reviewing quality, reporting, and best practices in {topic_label}",
                ],
            ),
            (
                "Advanced Workflow",
                "advanced",
                14,
                [
                    f"Advanced patterns in {topic_label}",
                    f"Operationalizing {topic_label} across teams",
                    f"Troubleshooting and optimization for {topic_label}",
                    f"Final capstone and delivery checklist for {topic_label}",
                ],
            ),
        )
        results: list[CourseRecord] = []
        for index, (track_name, level, duration_hours, syllabus) in enumerate(blueprints[:top_k], start=1):
            results.append(
                CourseRecord(
                    course_id=f"internal-{slug}-{index}",
                    title=f"{topic_label} {track_name}",
                    provider="EOI Learning Studio",
                    category="Custom Learning Path",
                    level=level,
                    duration_hours=duration_hours,
                    skills=topic_tokens,
                    tags=topic_tokens,
                    description=(
                        f"An in-app learning path generated for {topic_label}. "
                        "It gives the employee a structured way to start learning the exact topic they asked for inside the onboarding platform."
                    ),
                    url="",
                    delivery_mode="internal",
                    syllabus=syllabus,
                )
            )
        return results

    def is_course_query(self, message: str) -> bool:
        lowered = message.lower()
        return any(
            keyword in lowered
            for keyword in ("course", "courses", "learn", "learning", "training", "class", "classes")
        )

    def search_external(self, query: str, top_k: int = 10) -> list[CourseRecord]:
        try:
            return self.external_provider.search(query=query, top_k=top_k)
        except (httpx.HTTPError, OSError, ValueError):
            return NullExternalCourseProvider().search(query=query, top_k=top_k)

    def search(
        self,
        message: str,
        profile: EmployeeProfile,
        top_k: int = 3,
        progress: list[CourseProgressRecord] | None = None,
    ) -> list[CourseRecord]:
        progress = progress or []
        completed_ids = {item.course_id for item in progress if item.status == "completed"}
        started_ids = {item.course_id for item in progress if item.status == "in_progress"}
        saved_ids = {item.course_id for item in progress if item.saved_for_later}
        explicit_tokens = self._explicit_query_tokens(message)
        topic_tokens = self._ordered_topic_tokens(message)
        topic_token_set = set(topic_tokens)
        specific_tokens = self._specific_query_tokens(message)
        broad_topic_request = bool(topic_tokens) and not specific_tokens
        query_vector = Counter(_tokens(message))
        profile_weight = 0.05 if topic_tokens else 0.35
        for token in _tokens(" ".join(self._profile_context(profile))):
            query_vector[token] += profile_weight

        scored: list[tuple[float, CourseRecord]] = []
        for course in self.courses:
            if course.course_id in completed_ids:
                continue

            course_tokens = set(self.course_vectors[course.course_id].keys())
            if specific_tokens and not (specific_tokens & course_tokens):
                continue
            score = self._cosine_similarity(query_vector, self.course_vectors[course.course_id])
            exact_overlap = topic_token_set & course_tokens
            if exact_overlap:
                score += 0.22 * len(exact_overlap)
            elif topic_token_set:
                score -= 0.12

            if not broad_topic_request and not specific_tokens and profile.role.lower() in {tag.lower() for tag in course.tags}:
                score += 0.08
            if not broad_topic_request and not specific_tokens and profile.experience_level.lower() == course.level.lower():
                score += 0.05
            if set(skill.lower() for skill in profile.known_skills) & set(skill.lower() for skill in course.skills):
                score += 0.04
            if course.course_id in started_ids:
                score += 0.1
            if course.course_id in saved_ids:
                score += 0.05
            if score > 0.02:
                scored.append((score, course))

        scored.sort(key=lambda item: item[0], reverse=True)
        matched_courses = [course for _, course in scored[:top_k]]
        if not topic_tokens:
            return matched_courses

        overlap_matches = [
            course for course in matched_courses
            if topic_token_set & set(self.course_vectors[course.course_id].keys())
        ]
        if overlap_matches:
            if len(overlap_matches) >= top_k:
                return overlap_matches[:top_k]
            needed = top_k - len(overlap_matches)
            external_matches = self.search_external(self._format_topic_label(topic_tokens), top_k=needed)
            if external_matches:
                return overlap_matches + external_matches
            fallback = self._build_internal_topic_courses(topic_tokens, top_k=needed)
            return overlap_matches + fallback

        external_matches = self.search_external(self._format_topic_label(topic_tokens), top_k=top_k)
        if external_matches:
            return external_matches
        return self._build_internal_topic_courses(topic_tokens, top_k=top_k)
