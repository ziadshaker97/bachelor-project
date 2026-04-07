from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from ..config import MODULES_FILE, OULAD_SPLITS_FILE, OULAD_TRAINING_FILE, RECOMMENDATION_MODEL_FILE


HASH_DIMENSION = 256
ROLE_DEPARTMENT = {
    "Software Engineer": "Platform",
    "Data Analyst": "Analytics",
    "Operations Analyst": "Operations",
    "Product Manager": "Product",
}
ROLE_SKILLS = {
    "Software Engineer": ["python", "git"],
    "Data Analyst": ["sql", "data literacy"],
    "Operations Analyst": ["reporting", "workflow"],
    "Product Manager": ["communication", "roadmapping"],
}


def _stable_hash(value: str) -> int:
    total = 0
    for char in value:
        total = (total * 131 + ord(char)) % 1_000_003
    return total


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_modules() -> list[dict]:
    return _load_json(MODULES_FILE)  # type: ignore[return-value]


def _load_training_examples(path: Path = OULAD_TRAINING_FILE) -> list[dict]:
    return _load_json(path)  # type: ignore[return-value]


def _load_split_map(path: Path = OULAD_SPLITS_FILE) -> dict[str, str]:
    payload = _load_json(path)
    return {item["example_id"]: item["split"] for item in payload.get("assignments", [])}


def _profile_tokens(profile: dict[str, object]) -> list[str]:
    tokens: list[str] = []
    role = str(profile.get("role", "")).strip().lower()
    department = str(profile.get("department", "")).strip().lower()
    experience_level = str(profile.get("experience_level", "")).strip().lower()
    if role:
        tokens.append(f"role:{role}")
    if department:
        tokens.append(f"dept:{department}")
    if experience_level:
        tokens.append(f"exp:{experience_level}")
    for value in profile.get("known_skills", []):
        if str(value).strip():
            tokens.append(f"skill:{str(value).strip().lower()}")
    for value in profile.get("learning_preferences", []):
        if str(value).strip():
            tokens.append(f"pref:{str(value).strip().lower()}")
    return tokens


def _dense_vector(profile: dict[str, object], dimension: int = HASH_DIMENSION) -> list[float]:
    vector = [0.0] * dimension
    for token in _profile_tokens(profile):
        vector[_stable_hash(token) % dimension] += 1.0
    return vector


def _average(vectors: list[list[float]], dimension: int = HASH_DIMENSION) -> list[float]:
    if not vectors:
        return [0.0] * dimension
    totals = [0.0] * dimension
    for vector in vectors:
        for index, value in enumerate(vector):
            totals[index] += value
    return [value / len(vectors) for value in totals]


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _profile_from_example(example: dict) -> dict[str, object]:
    features = example["features"]
    role = example.get("role", "Operations Analyst")
    skills = []
    if float(features.get("assessment_score_weighted_mean", 0.0)) >= 75:
        skills.extend(ROLE_SKILLS.get(role, []))
    if int(features.get("clicks_forumng", 0)) >= 30:
        skills.append("communication")
    if int(features.get("clicks_resource", 0)) >= 20:
        skills.append("data literacy")

    preference_scores = {
        "interactive": int(features.get("clicks_quiz", 0)) + int(features.get("clicks_externalquiz", 0)),
        "text": int(features.get("clicks_resource", 0)) + int(features.get("clicks_page", 0)) + int(features.get("clicks_url", 0)),
        "video": int(features.get("clicks_oucontent", 0)) + int(features.get("clicks_homepage", 0)),
        "workshop": int(features.get("clicks_forumng", 0)) + int(features.get("clicks_ouwiki", 0)),
    }
    learning_preferences = [
        name
        for name, _ in sorted(preference_scores.items(), key=lambda item: item[1], reverse=True)
        if preference_scores[name] > 0
    ][:2]

    return {
        "role": role,
        "department": ROLE_DEPARTMENT.get(role, "Operations"),
        "experience_level": "intermediate" if int(features.get("studied_credits", 0)) >= 90 else "beginner",
        "known_skills": sorted({skill.lower() for skill in skills}),
        "learning_preferences": learning_preferences,
    }


def _heuristic_scores(profile: dict[str, object], modules: list[dict]) -> list[tuple[str, float]]:
    role = str(profile.get("role", "")).strip().lower()
    experience = str(profile.get("experience_level", "")).strip().lower()
    prefs = {str(item).strip().lower() for item in profile.get("learning_preferences", [])}
    skills = {str(item).strip().lower() for item in profile.get("known_skills", [])}
    scored: list[tuple[str, float]] = []
    for module in modules:
        score = 0.0
        if role in {tag.lower() for tag in module["role_tags"]}:
            score += 0.08
        if experience == module["difficulty"].lower():
            score += 0.05
        if module["format"].lower() in prefs:
            score += 0.05
        if any(prereq.lower() not in skills for prereq in module["prerequisites"]):
            score += 0.04
        score += 0.02 * sum(1 for tag in module["topic_tags"] if tag.lower() in skills)
        scored.append((module["module_id"], round(score, 4)))
    return sorted(scored, key=lambda item: item[1], reverse=True)


def train_recommendation_ranker(
    dataset_path: Path = OULAD_TRAINING_FILE,
    output: Path = RECOMMENDATION_MODEL_FILE,
) -> dict:
    examples = _load_training_examples(dataset_path)
    split_map = _load_split_map()
    modules = _load_modules()

    train_examples = [item for item in examples if split_map.get(item["example_id"], item.get("split")) == "train"]
    validation_examples = [item for item in examples if split_map.get(item["example_id"], item.get("split")) == "validation"]
    test_examples = [item for item in examples if split_map.get(item["example_id"], item.get("split")) == "test"]

    module_vectors: dict[str, list[list[float]]] = {}
    gap_vectors: dict[str, list[list[float]]] = {}
    for example in train_examples:
        vector = _dense_vector(_profile_from_example(example))
        module_vectors.setdefault(example["labels"]["next_best_module"], []).append(vector)
        gap_vectors.setdefault(example["labels"]["skill_gap"], []).append(vector)

    artifact = {
        "model_type": "profile_centroid_ranker",
        "target": "next_best_module",
        "skill_gap_target": "skill_gap",
        "hash_dimension": HASH_DIMENSION,
        "module_centroids": {label: _average(vectors) for label, vectors in module_vectors.items()},
        "skill_gap_centroids": {label: _average(vectors) for label, vectors in gap_vectors.items()},
        "module_metadata": {module["module_id"]: module for module in modules},
    }

    def evaluate(dataset: list[dict]) -> dict:
        model_top1 = model_top3 = heuristic_top1 = heuristic_top3 = gap_match = 0
        for example in dataset:
            profile = _profile_from_example(example)
            expected_module = example["labels"]["next_best_module"]
            expected_gap = example["labels"]["skill_gap"]
            model_scores, predicted_gap = predict_recommendations(profile, artifact, modules=modules, top_k=3)
            top_model = [item["module_id"] for item in model_scores]
            if top_model and top_model[0] == expected_module:
                model_top1 += 1
            if expected_module in top_model:
                model_top3 += 1
            if predicted_gap == expected_gap:
                gap_match += 1

            heuristic_ids = [module_id for module_id, _ in _heuristic_scores(profile, modules)[:3]]
            if heuristic_ids and heuristic_ids[0] == expected_module:
                heuristic_top1 += 1
            if expected_module in heuristic_ids:
                heuristic_top3 += 1

        total = len(dataset) or 1
        return {
            "top1_accuracy": round(model_top1 / total, 4),
            "top3_accuracy": round(model_top3 / total, 4),
            "skill_gap_accuracy": round(gap_match / total, 4),
            "heuristic_baseline": {
                "top1_accuracy": round(heuristic_top1 / total, 4),
                "top3_accuracy": round(heuristic_top3 / total, 4),
            },
        }

    artifact["generated_at"] = datetime.now(timezone.utc).isoformat()
    artifact["dataset"] = {
        "path": str(dataset_path),
        "split_file": str(OULAD_SPLITS_FILE),
        "train_examples": len(train_examples),
        "validation_examples": len(validation_examples),
        "test_examples": len(test_examples),
    }
    artifact["metrics"] = {
        "train": evaluate(train_examples),
        "validation": evaluate(validation_examples),
        "test": evaluate(test_examples),
    }

    _write_json(output, artifact)
    return artifact


def load_recommendation_ranker(path: Path = RECOMMENDATION_MODEL_FILE) -> dict:
    return _load_json(path)  # type: ignore[return-value]


def predict_recommendations(
    profile: dict[str, object],
    artifact: dict | None = None,
    modules: list[dict] | None = None,
    top_k: int = 5,
) -> tuple[list[dict], str]:
    model = artifact or load_recommendation_ranker()
    available_modules = modules or list(model["module_metadata"].values())
    vector = _dense_vector(profile, int(model.get("hash_dimension", HASH_DIMENSION)))

    scores: list[dict] = []
    for module in available_modules:
        centroid = model["module_centroids"].get(module["module_id"])
        score = _cosine(vector, centroid) if centroid else 0.0
        role = str(profile.get("role", "")).strip().lower()
        if role and role in {tag.lower() for tag in module["role_tags"]}:
            score += 0.05
        scores.append({"module_id": module["module_id"], "score": round(score, 4)})
    scores.sort(key=lambda item: item["score"], reverse=True)

    gap_scores = {
        gap: _cosine(vector, centroid)
        for gap, centroid in model.get("skill_gap_centroids", {}).items()
    }
    predicted_gap = max(gap_scores.items(), key=lambda item: item[1])[0] if gap_scores else "workflow"
    return scores[:top_k], predicted_gap


class LocalRecommendationModelService:
    def __init__(self, artifact_path: Path = RECOMMENDATION_MODEL_FILE) -> None:
        self.artifact_path = artifact_path
        self._artifact: dict | None = None

    def load_model(self) -> dict:
        if self._artifact is None:
            self._artifact = load_recommendation_ranker(self.artifact_path)
        return self._artifact

    def predict(self, profile: dict[str, object], top_k: int = 5) -> tuple[list[dict], str]:
        artifact = self.load_model()
        return predict_recommendations(profile, artifact=artifact, top_k=top_k)
