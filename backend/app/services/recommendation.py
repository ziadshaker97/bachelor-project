import math
from collections import Counter

from ..models import EmployeeProfile, RecommendationResult, TrainingModule
from ..seed import load_modules, load_oulad_profiles
from .recommender_model import LocalRecommendationModelService


class RecommendationService:
    HIDDEN_MODULE_IDS = {"mod-security-101", "mod-hr-policy", "mod-customer-context"}

    def __init__(self) -> None:
        self.modules = load_modules()
        self.reference_profiles = load_oulad_profiles()
        self.model_service = LocalRecommendationModelService()

    @staticmethod
    def _normalize(tokens: list[str]) -> list[str]:
        return [token.strip().lower() for token in tokens if token.strip()]

    def _profile_vector(self, profile: EmployeeProfile) -> Counter[str]:
        vector: Counter[str] = Counter()
        vector.update(f"role:{value}" for value in self._normalize([profile.role]))
        vector.update(f"dept:{value}" for value in self._normalize([profile.department]))
        vector.update(f"exp:{value}" for value in self._normalize([profile.experience_level]))
        vector.update(f"skill:{value}" for value in self._normalize(profile.known_skills))
        vector.update(f"pref:{value}" for value in self._normalize(profile.learning_preferences))
        vector.update(f"goal:{value}" for value in self._normalize(profile.career_goals))
        vector.update(self._normalize(profile.cv_summary.replace(",", " ").split()))
        if profile.months_in_training >= 6:
            vector.update(["history:advanced", "history:advanced"])
        elif profile.months_in_training >= 3:
            vector.update(["history:steady"])
        else:
            vector.update(["history:early"])

        for item in self.reference_profiles:
            if item["role"].lower() == profile.role.lower():
                vector.update(f"topic:{value}" for value in self._normalize(item["recommended_topics"]))
                vector.update(f"gap:{value}" for value in self._normalize(item["common_skill_gaps"]))
        return vector

    def _module_vector(self, module: TrainingModule) -> Counter[str]:
        vector: Counter[str] = Counter()
        vector.update(f"topic:{value}" for value in self._normalize(module.topic_tags))
        vector.update(f"role:{value}" for value in self._normalize(module.role_tags))
        vector.update(f"format:{value}" for value in self._normalize([module.format]))
        vector.update(f"diff:{value}" for value in self._normalize([module.difficulty]))
        vector.update(f"req:{value}" for value in self._normalize(module.prerequisites))
        description_tokens = self._normalize(module.description.replace(",", " ").split())
        vector.update(description_tokens)
        return vector

    def _is_module_relevant(self, profile: EmployeeProfile, module: TrainingModule) -> bool:
        if module.module_id in self.HIDDEN_MODULE_IDS:
            return False
        role = profile.role.lower()
        department = profile.department.lower()
        module_roles = {value.lower() for value in module.role_tags}
        module_topics = {value.lower() for value in module.topic_tags}
        return (
            role in module_roles
            or department in module_topics
        )

    @staticmethod
    def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
        keys = set(left) | set(right)
        dot = sum(left[key] * right[key] for key in keys)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _explain(self, profile: EmployeeProfile, module: TrainingModule) -> tuple[list[str], str]:
        reasons: list[str] = []
        text_fragments: list[str] = []

        module_topics = {value.lower() for value in module.topic_tags}
        module_roles = {value.lower() for value in module.role_tags}
        profile_skills = {value.lower() for value in profile.known_skills}
        profile_prefs = {value.lower() for value in profile.learning_preferences}

        if profile.role.lower() in module_roles:
            reasons.append("matched_role")
            text_fragments.append("aligned with your role")
        if profile.career_goals and module_topics & {value.lower() for value in profile.career_goals}:
            reasons.append("career_goal")
            text_fragments.append("supports one of your stated career goals")
        if profile.experience_level.lower() == module.difficulty.lower():
            reasons.append("difficulty_fit")
            text_fragments.append("fits your current experience level")
        if module.format.lower() in profile_prefs:
            reasons.append("learning_preference")
            text_fragments.append(f"matches your preferred {module.format.lower()} format")
        missing_prereqs = [item for item in module.prerequisites if item.lower() not in profile_skills]
        if missing_prereqs:
            reasons.append("skill_gap")
            text_fragments.append(f"helps close the skill gap around {missing_prereqs[0]}")
        elif module_topics & profile_skills:
            reasons.append("skill_continuity")
            text_fragments.append("extends topics you already know")
        if not reasons:
            reasons.append("general_relevance")
            text_fragments.append("relevant to typical onboarding needs for similar employees")
        return reasons, "; ".join(text_fragments)

    def _heuristic_recommend(self, profile: EmployeeProfile, top_k: int = 5) -> list[RecommendationResult]:
        profile_vector = self._profile_vector(profile)
        scored: list[RecommendationResult] = []
        for module in self.modules:
            if not self._is_module_relevant(profile, module):
                continue
            score = self._cosine_similarity(profile_vector, self._module_vector(module))
            if profile.role.lower() in {value.lower() for value in module.role_tags}:
                score += 0.08
            if module.format.lower() in {value.lower() for value in profile.learning_preferences}:
                score += 0.05
            missing_prereqs = [
                item for item in module.prerequisites
                if item.lower() not in {value.lower() for value in profile.known_skills}
            ]
            if missing_prereqs:
                score += 0.04
            reasons, text = self._explain(profile, module)
            scored.append(
                RecommendationResult(
                    module_id=module.module_id,
                    score=round(score, 4),
                    reason_codes=reasons,
                    reason_text=text,
                )
            )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

    def _model_recommend(self, profile: EmployeeProfile, top_k: int = 5) -> list[RecommendationResult]:
        ranked, predicted_gap = self.model_service.predict(
            {
                "role": profile.role,
                "department": profile.department,
                "experience_level": profile.experience_level,
                "known_skills": profile.known_skills,
                "learning_preferences": profile.learning_preferences,
            },
            top_k=max(top_k * 3, len(self.modules)),
        )
        module_by_id = {module.module_id: module for module in self.modules}
        recommendations: list[RecommendationResult] = []
        profile_skills = {value.lower() for value in profile.known_skills}
        profile_goals = {value.lower() for value in profile.career_goals}
        seen_ids: set[str] = set()
        for item in ranked:
            module = module_by_id.get(item["module_id"])
            if module is None:
                continue
            if not self._is_module_relevant(profile, module):
                continue
            if module.module_id in seen_ids:
                continue
            score = float(item["score"])
            module_roles = {value.lower() for value in module.role_tags}
            module_topics = {value.lower() for value in module.topic_tags}
            if profile.role.lower() in module_roles:
                score += 0.18
            if profile.department.lower() in module_topics:
                score += 0.08
            if module_topics & profile_goals:
                score += 0.12
            missing_prereqs = [item for item in module.prerequisites if item.lower() not in profile_skills]
            if missing_prereqs:
                score += 0.05
            reason_codes = ["local_model"]
            reason_text = f"Predicted next-best module from the local recommender model; likely skill gap: {predicted_gap}."
            if profile.role.lower() in {value.lower() for value in module.role_tags}:
                reason_codes.append("matched_role")
            if module.format.lower() in {value.lower() for value in profile.learning_preferences}:
                reason_codes.append("learning_preference")
            recommendations.append(
                RecommendationResult(
                    module_id=module.module_id,
                    score=round(score, 4),
                    reason_codes=reason_codes,
                    reason_text=reason_text,
                )
            )
            seen_ids.add(module.module_id)
        recommendations.sort(key=lambda item: item.score, reverse=True)
        return recommendations[:top_k]

    def recommend(self, profile: EmployeeProfile, top_k: int = 5) -> list[RecommendationResult]:
        return self.recommend_with_strategy(profile=profile, top_k=top_k)[0]

    def recommend_with_strategy(self, profile: EmployeeProfile, top_k: int = 5) -> tuple[list[RecommendationResult], str]:
        try:
            model_results = self._model_recommend(profile=profile, top_k=top_k)
            if len(model_results) >= top_k:
                return model_results, "model"

            heuristic_results = self._heuristic_recommend(profile=profile, top_k=top_k)
            merged: list[RecommendationResult] = []
            seen_ids: set[str] = set()
            for item in [*model_results, *heuristic_results]:
                if item.module_id in seen_ids:
                    continue
                merged.append(item)
                seen_ids.add(item.module_id)
                if len(merged) >= top_k:
                    break
            return merged, "hybrid"
        except Exception:
            return self._heuristic_recommend(profile=profile, top_k=top_k), "heuristic"
