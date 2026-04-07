from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from ..config import (
    DOC2DIAL_BEHAVIOR_FILE,
    DOC2DIAL_FILE,
    DOC2DIAL_RAW_DIR,
    OULAD_FILE,
    OULAD_RAW_DIR,
    OULAD_SPLITS_FILE,
    OULAD_TRAINING_FILE,
    PROCESSED_DIR,
    SOURCES_METADATA_FILE,
)


REQUIRED_OULAD_FILES = {
    "courses.csv",
    "assessments.csv",
    "studentAssessment.csv",
    "studentInfo.csv",
    "studentRegistration.csv",
    "studentVle.csv",
    "vle.csv",
}

REQUIRED_DOC2DIAL_FILES = {
    "doc2dial_dial_train.json",
    "doc2dial_dial_validation.json",
    "doc2dial_dial_test.json",
    "doc2dial_doc.json",
}

ROLE_BY_MODULE = {
    "AAA": "Software Engineer",
    "BBB": "Data Analyst",
    "CCC": "Product Manager",
    "DDD": "Operations Analyst",
    "EEE": "Software Engineer",
    "FFF": "Data Analyst",
    "GGG": "Product Manager",
}

ACTIVITY_TO_TOPIC = {
    "forumng": "communication",
    "homepage": "workflow",
    "oucontent": "guided learning",
    "quiz": "assessment readiness",
    "resource": "knowledge navigation",
    "subpage": "self-service discovery",
    "url": "tool usage",
    "externalquiz": "knowledge checks",
    "page": "documentation fluency",
    "questionnaire": "feedback loops",
    "ouwiki": "collaboration",
}

ASSESSMENT_TO_GAP = {
    "CMA": "continuous learning discipline",
    "Exam": "assessment readiness",
    "TMA": "applied knowledge",
}

DOC2DIAL_STYLE_BY_DA = {
    "respond_solution": "Respond with a grounded solution using the cited document spans and give actionable next steps.",
    "respond_no_solution": "State clearly that no grounded solution is available for the described condition.",
    "respond_ood": "State clearly that the query is out of domain for the document and do not invent an answer.",
    "query_condition": "Clarify whether the condition in the document applies before offering a solution.",
    "query_solution": "Answer directly from the relevant solution span in the document.",
}

SUCCESS_SCORE_BY_RESULT = {
    "Distinction": 1.0,
    "Pass": 0.8,
    "Fail": 0.25,
    "Withdrawn": 0.0,
}

ROLE_DEFAULT_MODULE = {
    "Software Engineer": "mod-eng-stack",
    "Data Analyst": "mod-data-governance",
    "Operations Analyst": "mod-data-governance",
    "Product Manager": "mod-product-collab",
}

DOC2DIAL_BEHAVIOR_BY_DA = {
    "respond_solution": "grounded_answer",
    "query_solution": "grounded_answer",
    "query_condition": "clarifying_follow_up",
    "respond_no_solution": "unsupported",
    "respond_ood": "unsupported",
}

EARLY_WINDOW_RATIO = 0.25
OUTLIER_LOW_QUANTILE = 0.01
OUTLIER_HIGH_QUANTILE = 0.99
OUTLIER_NUMERIC_FEATURE_EXACT = {
    "studied_credits",
    "num_prev_attempts",
    "module_presentation_length",
    "early_window_days",
    "days_registered_before_start",
    "registered_late",
    "unregistered",
    "days_until_unregistration",
    "total_vle_clicks",
    "early_vle_clicks",
    "prestart_vle_clicks",
    "active_vle_days",
    "early_active_vle_days",
    "assessments_submitted",
    "assessments_banked",
    "late_assessment_submissions",
    "assessment_score_mean",
    "assessment_score_weighted_mean",
    "early_assessments_submitted",
    "early_assessment_score_mean",
    "early_assessment_score_weighted_mean",
}
OUTLIER_NUMERIC_FEATURE_SUFFIXES = (
    "_score_mean",
)
OUTLIER_NUMERIC_FEATURE_PREFIXES = (
    "clicks_",
    "early_clicks_",
)


def _ensure_processed_dir() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _safe_int(value: str | None, default: int = 0) -> int:
    if value in {None, "", "?"}:
        return default
    return int(float(value))


def _safe_float(value: str | None, default: float = 0.0) -> float:
    if value in {None, "", "?"}:
        return default
    return float(value)


def _early_window_days(module_length: int) -> int:
    return max(1, int(round(module_length * EARLY_WINDOW_RATIO)))


def _quantile(sorted_values: list[float], quantile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * quantile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    weight = position - lower_index
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + (upper - lower) * weight


def _should_clip_training_feature(feature_name: str, value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return (
        feature_name in OUTLIER_NUMERIC_FEATURE_EXACT
        or feature_name.startswith(OUTLIER_NUMERIC_FEATURE_PREFIXES)
        or feature_name.endswith(OUTLIER_NUMERIC_FEATURE_SUFFIXES)
    )


def _clip_training_feature_outliers(examples: list[dict]) -> dict[str, dict[str, float]]:
    numeric_values: defaultdict[str, list[float]] = defaultdict(list)
    for example in examples:
        for feature_name, value in example["features"].items():
            if _should_clip_training_feature(feature_name, value):
                numeric_values[feature_name].append(float(value))

    clip_bounds: dict[str, dict[str, float]] = {}
    for feature_name, values in numeric_values.items():
        sorted_values = sorted(values)
        lower_bound = _quantile(sorted_values, OUTLIER_LOW_QUANTILE)
        upper_bound = _quantile(sorted_values, OUTLIER_HIGH_QUANTILE)
        clip_bounds[feature_name] = {
            "lower_bound": round(lower_bound, 4),
            "upper_bound": round(upper_bound, 4),
        }

    for example in examples:
        for feature_name, bounds in clip_bounds.items():
            value = example["features"].get(feature_name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            clipped = min(max(float(value), bounds["lower_bound"]), bounds["upper_bound"])
            example["features"][feature_name] = int(round(clipped)) if isinstance(value, int) else round(clipped, 4)

    return clip_bounds


def _stable_bucket(value: str, modulo: int = 10_000) -> int:
    total = 0
    for char in value:
        total = (total * 131 + ord(char)) % modulo
    return total


def _assign_split(example_id: str) -> str:
    bucket = _stable_bucket(example_id)
    if bucket < 7_000:
        return "train"
    if bucket < 8_500:
        return "validation"
    return "test"


def _derive_skill_gap_and_module(role: str, features: dict[str, object], final_result: str) -> tuple[str, str]:
    score = float(features.get("assessment_score_weighted_mean", 0.0))
    late_submissions = int(features.get("late_assessment_submissions", 0))
    early_active_days = int(features.get("early_active_vle_days", 0))
    total_clicks = int(features.get("total_vle_clicks", 0))
    registered_late = int(features.get("registered_late", 0))
    unregistered = int(features.get("unregistered", 0))
    forum_clicks = int(features.get("clicks_forumng", 0))
    homepage_clicks = int(features.get("clicks_homepage", 0))
    resource_clicks = int(features.get("clicks_resource", 0))
    quiz_score = float(features.get("tma_score_mean", 0.0) or features.get("exam_score_mean", 0.0))

    if final_result == "Withdrawn" or unregistered or registered_late or late_submissions >= 3:
        return "workflow", "mod-hr-policy"
    if role == "Software Engineer":
        if score < 65 or quiz_score < 60:
            return "development", "mod-eng-stack"
        if early_active_days < 8 or total_clicks < 120:
            return "security awareness", "mod-security-101"
        return "customer empathy", "mod-customer-context"
    if role in {"Data Analyst", "Operations Analyst"}:
        if score < 65 or resource_clicks < 20:
            return "data governance", "mod-data-governance"
        if early_active_days < 8:
            return "compliance", "mod-security-101"
        return "workflow", "mod-customer-context"
    if role == "Product Manager":
        if score < 70 or forum_clicks + homepage_clicks < 120:
            return "stakeholder management", "mod-product-collab"
        if early_active_days < 8:
            return "workflow", "mod-hr-policy"
        return "communication", "mod-customer-context"
    return "security awareness", ROLE_DEFAULT_MODULE.get(role, "mod-security-101")


def build_oulad_split_artifact(
    examples: list[dict],
    output: Path = OULAD_SPLITS_FILE,
) -> dict:
    assignments = []
    split_counts: Counter[str] = Counter()
    for example in examples:
        split = _assign_split(example["example_id"])
        assignments.append({"example_id": example["example_id"], "split": split})
        split_counts[split] += 1
        example["split"] = split

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "split_strategy": "stable_hash_bucket",
        "ratios": {"train": 0.70, "validation": 0.15, "test": 0.15},
        "counts": dict(split_counts),
        "assignments": assignments,
    }
    _write_json(output, payload)
    return payload


def validate_oulad_raw(raw_dir: Path = OULAD_RAW_DIR) -> None:
    missing = sorted(name for name in REQUIRED_OULAD_FILES if not (raw_dir / name).exists())
    if missing:
        raise FileNotFoundError(f"Missing OULAD raw files: {', '.join(missing)}")


def validate_doc2dial_raw(raw_dir: Path = DOC2DIAL_RAW_DIR) -> None:
    missing = sorted(name for name in REQUIRED_DOC2DIAL_FILES if not (raw_dir / name).exists())
    if missing:
        raise FileNotFoundError(f"Missing Doc2Dial raw files: {', '.join(missing)}")


def _module_key(row: dict[str, str]) -> tuple[str, str]:
    return (row["code_module"], row["code_presentation"])


def prepare_oulad_artifacts(raw_dir: Path = OULAD_RAW_DIR, output: Path = OULAD_FILE) -> list[dict]:
    validate_oulad_raw(raw_dir)
    _ensure_processed_dir()

    student_info = _read_csv(raw_dir / "studentInfo.csv")
    student_vle = _read_csv(raw_dir / "studentVle.csv")
    vle = _read_csv(raw_dir / "vle.csv")
    assessments = _read_csv(raw_dir / "assessments.csv")
    student_assessment = _read_csv(raw_dir / "studentAssessment.csv")

    site_activity: dict[tuple[str, str, str], str] = {}
    for row in vle:
        site_activity[(row["id_site"], row["code_module"], row["code_presentation"])] = row["activity_type"]

    assessment_type_by_id = {row["id_assessment"]: row["assessment_type"] for row in assessments}

    student_role: dict[tuple[str, str, str], str] = {}
    role_students: defaultdict[str, set[str]] = defaultdict(set)
    role_pass_total: Counter[str] = Counter()
    role_total: Counter[str] = Counter()
    role_topics: Counter[tuple[str, str]] = Counter()
    role_gaps: Counter[tuple[str, str]] = Counter()
    role_clicks: defaultdict[str, list[int]] = defaultdict(list)
    role_credits: defaultdict[str, list[int]] = defaultdict(list)

    for row in student_info:
        role = ROLE_BY_MODULE.get(row["code_module"])
        if not role:
            continue
        student_key = (row["code_module"], row["code_presentation"], row["id_student"])
        student_role[student_key] = role
        role_students[role].add(row["id_student"])
        role_total[role] += 1
        if row["final_result"] in {"Pass", "Distinction"}:
            role_pass_total[role] += 1
        role_credits[role].append(int(row["studied_credits"]))
        if row["final_result"] in {"Fail", "Withdrawn"}:
            role_gaps[(role, "time management")] += 1

    for row in student_vle:
        key = (row["code_module"], row["code_presentation"], row["id_student"])
        role = student_role.get(key)
        if not role:
            continue
        activity = site_activity.get((row["id_site"], row["code_module"], row["code_presentation"]))
        if not activity:
            continue
        topic = ACTIVITY_TO_TOPIC.get(activity, activity.lower())
        clicks = int(row["sum_click"])
        role_topics[(role, topic)] += clicks
        role_clicks[role].append(clicks)

    student_assessment_scores: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    for row in student_assessment:
        assessment_type = assessment_type_by_id.get(row["id_assessment"])
        if not assessment_type or row["score"] in {"", "?"}:
            continue
        # assessment data is keyed only by student and id_assessment, so map the gap globally by assessment type
        student_assessment_scores[(row["id_student"], assessment_type)].append(float(row["score"]))

    students_by_role: defaultdict[str, set[str]] = defaultdict(set)
    for (_, _, student_id), role in student_role.items():
        students_by_role[role].add(student_id)

    for role, students in students_by_role.items():
        for assessment_type, gap_name in ASSESSMENT_TO_GAP.items():
            relevant_scores = [
                score
                for (student_id, row_type), scores in student_assessment_scores.items()
                if student_id in students and row_type == assessment_type
                for score in scores
            ]
            if relevant_scores:
                avg_score = sum(relevant_scores) / len(relevant_scores)
                role_gaps[(role, gap_name)] += int(max(0, 100 - avg_score))

    transformed: list[dict] = []
    for role in sorted(role_students):
        topics = [
            topic
            for role_name, topic in [item[0] for item in role_topics.most_common()]
            if role_name == role
        ]
        gaps = [
            gap
            for role_name, gap in [item[0] for item in role_gaps.most_common()]
            if role_name == role
        ]
        avg_clicks = sum(role_clicks[role]) / len(role_clicks[role]) if role_clicks[role] else 0
        avg_credits = sum(role_credits[role]) / len(role_credits[role]) if role_credits[role] else 0
        pass_rate = role_pass_total[role] / role_total[role] if role_total[role] else 0
        learner_clusters = []
        if avg_clicks >= 15:
            learner_clusters.append("high_engagement")
        else:
            learner_clusters.append("steady_engagement")
        learner_clusters.append("successful_progression" if pass_rate >= 0.7 else "support_needed")
        difficulty_progression = "intermediate" if avg_credits >= 90 else "beginner"

        transformed.append(
            {
                "role": role,
                "employee_cluster": role.lower().replace(" ", "_"),
                "recommended_topics": topics[:4] or ["workflow", "guided learning"],
                "common_skill_gaps": gaps[:4] or ["time management", "assessment readiness"],
                "normalized_engagement_score": round(min(1.0, avg_clicks / 25), 2),
                "topic_affinity": topics[:6] or ["workflow"],
                "difficulty_progression": difficulty_progression,
                "learner_clusters": learner_clusters,
                "source_counts": {
                    "students": len(role_students[role]),
                    "avg_studied_credits": round(avg_credits, 2),
                    "pass_rate": round(pass_rate, 2),
                },
            }
        )

    _write_json(output, transformed)
    return transformed


def prepare_oulad_training_artifacts(
    raw_dir: Path = OULAD_RAW_DIR,
    output: Path = OULAD_TRAINING_FILE,
) -> list[dict]:
    validate_oulad_raw(raw_dir)
    _ensure_processed_dir()

    student_info = _read_csv(raw_dir / "studentInfo.csv")
    student_vle = _read_csv(raw_dir / "studentVle.csv")
    student_registration = _read_csv(raw_dir / "studentRegistration.csv")
    assessments = _read_csv(raw_dir / "assessments.csv")
    student_assessment = _read_csv(raw_dir / "studentAssessment.csv")
    courses = _read_csv(raw_dir / "courses.csv")
    vle = _read_csv(raw_dir / "vle.csv")

    module_lengths = {
        _module_key(row): _safe_int(row["module_presentation_length"], default=0)
        for row in courses
    }
    registration_by_student = {
        (row["code_module"], row["code_presentation"], row["id_student"]): row
        for row in student_registration
    }
    activity_by_site = {
        (row["id_site"], row["code_module"], row["code_presentation"]): row["activity_type"].lower()
        for row in vle
    }
    activity_types = sorted({row["activity_type"].lower() for row in vle if row["activity_type"]})

    assessment_meta = {
        row["id_assessment"]: {
            "module_key": _module_key(row),
            "assessment_type": row["assessment_type"],
            "assessment_date": _safe_int(row["date"], default=-1),
            "weight": _safe_float(row["weight"], default=0.0),
        }
        for row in assessments
    }
    assessment_types = sorted({row["assessment_type"] for row in assessments if row["assessment_type"]})

    vle_by_student: defaultdict[tuple[str, str, str], dict[str, object]] = defaultdict(
        lambda: {
            "total_clicks": 0,
            "early_clicks": 0,
            "prestart_clicks": 0,
            "active_days": set(),
            "early_active_days": set(),
            "activity_clicks": Counter(),
            "early_activity_clicks": Counter(),
        }
    )

    for row in student_vle:
        student_key = (row["code_module"], row["code_presentation"], row["id_student"])
        module_length = module_lengths.get((row["code_module"], row["code_presentation"]), 0)
        early_window = _early_window_days(module_length if module_length > 0 else 100)
        date = _safe_int(row["date"], default=0)
        clicks = _safe_int(row["sum_click"], default=0)
        activity = activity_by_site.get(
            (row["id_site"], row["code_module"], row["code_presentation"]),
            "unknown",
        )
        metrics = vle_by_student[student_key]
        metrics["total_clicks"] += clicks
        cast(Counter, metrics["activity_clicks"])[activity] += clicks
        cast(set[int], metrics["active_days"]).add(date)
        if date < 0:
            metrics["prestart_clicks"] += clicks
        if date <= early_window:
            metrics["early_clicks"] += clicks
            cast(Counter, metrics["early_activity_clicks"])[activity] += clicks
            cast(set[int], metrics["early_active_days"]).add(date)

    assessments_by_student: defaultdict[tuple[str, str, str], dict[str, object]] = defaultdict(
        lambda: {
            "submitted_count": 0,
            "banked_count": 0,
            "late_count": 0,
            "weighted_score_sum": 0.0,
            "weight_total": 0.0,
            "score_sum": 0.0,
            "score_count": 0,
            "early_submitted_count": 0,
            "early_weighted_score_sum": 0.0,
            "early_weight_total": 0.0,
            "early_score_sum": 0.0,
            "early_score_count": 0,
            "type_score_sum": Counter(),
            "type_score_count": Counter(),
            "early_type_score_sum": Counter(),
            "early_type_score_count": Counter(),
        }
    )

    for row in student_assessment:
        meta = assessment_meta.get(row["id_assessment"])
        if not meta:
            continue
        module_key = cast(tuple[str, str], meta["module_key"])
        student_key = (module_key[0], module_key[1], row["id_student"])
        module_length = module_lengths.get(module_key, 0)
        early_window = _early_window_days(module_length if module_length > 0 else 100)
        score = _safe_float(row["score"], default=-1.0)
        submitted_day = _safe_int(row["date_submitted"], default=-1)
        weight = cast(float, meta["weight"])
        assessment_type = cast(str, meta["assessment_type"])
        assessment_date = cast(int, meta["assessment_date"])

        metrics = assessments_by_student[student_key]
        metrics["submitted_count"] += 1
        metrics["banked_count"] += _safe_int(row["is_banked"], default=0)
        if assessment_date >= 0 and submitted_day > assessment_date:
            metrics["late_count"] += 1

        if score >= 0:
            metrics["score_sum"] += score
            metrics["score_count"] += 1
            metrics["weighted_score_sum"] += score * weight
            metrics["weight_total"] += weight
            cast(Counter, metrics["type_score_sum"])[assessment_type] += score
            cast(Counter, metrics["type_score_count"])[assessment_type] += 1

        is_early = (
            (assessment_date >= 0 and assessment_date <= early_window)
            or (submitted_day >= 0 and submitted_day <= early_window)
        )
        if is_early:
            metrics["early_submitted_count"] += 1
            if score >= 0:
                metrics["early_score_sum"] += score
                metrics["early_score_count"] += 1
                metrics["early_weighted_score_sum"] += score * weight
                metrics["early_weight_total"] += weight
                cast(Counter, metrics["early_type_score_sum"])[assessment_type] += score
                cast(Counter, metrics["early_type_score_count"])[assessment_type] += 1

    training_examples: list[dict] = []
    for row in student_info:
        module_key = _module_key(row)
        student_key = (row["code_module"], row["code_presentation"], row["id_student"])
        module_length = module_lengths.get(module_key, 0)
        early_window = _early_window_days(module_length if module_length > 0 else 100)
        registration = registration_by_student.get(student_key, {})
        vle_metrics = vle_by_student[student_key]
        assessment_metrics = assessments_by_student[student_key]

        registration_day = _safe_int(registration.get("date_registration"), default=0)
        unregistration_day = _safe_int(registration.get("date_unregistration"), default=-1)
        score_count = cast(int, assessment_metrics["score_count"])
        early_score_count = cast(int, assessment_metrics["early_score_count"])
        submitted_count = cast(int, assessment_metrics["submitted_count"])

        feature_row = {
            "gender": row["gender"],
            "region": row["region"],
            "highest_education": row["highest_education"],
            "imd_band": row["imd_band"],
            "age_band": row["age_band"],
            "disability": row["disability"],
            "studied_credits": _safe_int(row["studied_credits"], default=0),
            "num_prev_attempts": _safe_int(row["num_of_prev_attempts"], default=0),
            "module_code": row["code_module"],
            "presentation_code": row["code_presentation"],
            "module_presentation_length": module_length,
            "early_window_days": early_window,
            "days_registered_before_start": abs(registration_day) if registration_day < 0 else 0,
            "registered_late": int(registration_day > 0),
            "unregistered": int(unregistration_day >= 0),
            "days_until_unregistration": unregistration_day if unregistration_day >= 0 else module_length,
            "total_vle_clicks": cast(int, vle_metrics["total_clicks"]),
            "early_vle_clicks": cast(int, vle_metrics["early_clicks"]),
            "prestart_vle_clicks": cast(int, vle_metrics["prestart_clicks"]),
            "active_vle_days": len(cast(set[int], vle_metrics["active_days"])),
            "early_active_vle_days": len(cast(set[int], vle_metrics["early_active_days"])),
            "assessments_submitted": submitted_count,
            "assessments_banked": cast(int, assessment_metrics["banked_count"]),
            "late_assessment_submissions": cast(int, assessment_metrics["late_count"]),
            "assessment_score_mean": round(
                cast(float, assessment_metrics["score_sum"]) / score_count,
                4,
            ) if score_count else 0.0,
            "assessment_score_weighted_mean": round(
                cast(float, assessment_metrics["weighted_score_sum"]) / cast(float, assessment_metrics["weight_total"]),
                4,
            ) if cast(float, assessment_metrics["weight_total"]) else 0.0,
            "early_assessments_submitted": cast(int, assessment_metrics["early_submitted_count"]),
            "early_assessment_score_mean": round(
                cast(float, assessment_metrics["early_score_sum"]) / early_score_count,
                4,
            ) if early_score_count else 0.0,
            "early_assessment_score_weighted_mean": round(
                cast(float, assessment_metrics["early_weighted_score_sum"]) / cast(float, assessment_metrics["early_weight_total"]),
                4,
            ) if cast(float, assessment_metrics["early_weight_total"]) else 0.0,
        }

        activity_clicks = cast(Counter, vle_metrics["activity_clicks"])
        early_activity_clicks = cast(Counter, vle_metrics["early_activity_clicks"])
        for activity_type in activity_types:
            feature_row[f"clicks_{activity_type}"] = activity_clicks.get(activity_type, 0)
            feature_row[f"early_clicks_{activity_type}"] = early_activity_clicks.get(activity_type, 0)

        type_score_sum = cast(Counter, assessment_metrics["type_score_sum"])
        type_score_count = cast(Counter, assessment_metrics["type_score_count"])
        early_type_score_sum = cast(Counter, assessment_metrics["early_type_score_sum"])
        early_type_score_count = cast(Counter, assessment_metrics["early_type_score_count"])
        for assessment_type in assessment_types:
            feature_row[f"{assessment_type.lower()}_score_mean"] = round(
                type_score_sum.get(assessment_type, 0.0) / type_score_count.get(assessment_type, 1),
                4,
            ) if type_score_count.get(assessment_type, 0) else 0.0
            feature_row[f"early_{assessment_type.lower()}_score_mean"] = round(
                early_type_score_sum.get(assessment_type, 0.0) / early_type_score_count.get(assessment_type, 1),
                4,
            ) if early_type_score_count.get(assessment_type, 0) else 0.0

        final_result = row["final_result"]
        role = ROLE_BY_MODULE.get(row["code_module"], "Operations Analyst")
        skill_gap, next_best_module = _derive_skill_gap_and_module(role, feature_row, final_result)
        training_examples.append(
            {
                "example_id": f"{row['code_module']}_{row['code_presentation']}_{row['id_student']}",
                "student_id": row["id_student"],
                "target_module": row["code_module"],
                "target_presentation": row["code_presentation"],
                "role": role,
                "features": feature_row,
                "labels": {
                    "final_result": final_result,
                    "completed": int(final_result != "Withdrawn"),
                    "success": int(final_result in {"Pass", "Distinction"}),
                    "distinction": int(final_result == "Distinction"),
                    "withdrawn": int(final_result == "Withdrawn"),
                    "recommendation_score": SUCCESS_SCORE_BY_RESULT.get(final_result, 0.0),
                    "next_best_module": next_best_module,
                    "skill_gap": skill_gap,
                },
            }
        )

    _clip_training_feature_outliers(training_examples)
    build_oulad_split_artifact(training_examples, output=output.parent / OULAD_SPLITS_FILE.name)
    for example in training_examples:
        example["outlier_handling"] = {
            "method": "winsorized_quantile_clip",
            "low_quantile": OUTLIER_LOW_QUANTILE,
            "high_quantile": OUTLIER_HIGH_QUANTILE,
        }

    _write_json(output, training_examples)
    return training_examples


def prepare_doc2dial_artifacts(raw_dir: Path = DOC2DIAL_RAW_DIR, output: Path = DOC2DIAL_FILE) -> list[dict]:
    validate_doc2dial_raw(raw_dir)
    _ensure_processed_dir()

    doc_payload = json.loads((raw_dir / "doc2dial_doc.json").read_text(encoding="utf-8"))
    documents = doc_payload["doc_data"]
    examples: list[dict] = []

    for split in ("train", "validation", "test"):
        dial_path = raw_dir / f"doc2dial_dial_{split}.json"
        dial_payload = json.loads(dial_path.read_text(encoding="utf-8"))
        for domain, docs in dial_payload["dial_data"].items():
            for doc_id, dialogs in docs.items():
                doc_title = documents.get(domain, {}).get(doc_id, {}).get("title", doc_id)
                for dialog in dialogs:
                    turns = dialog.get("turns", [])
                    for index in range(len(turns) - 1):
                        current_turn = turns[index]
                        next_turn = turns[index + 1]
                        if current_turn.get("role") != "user" or next_turn.get("role") != "agent":
                            continue
                        style_hint = DOC2DIAL_STYLE_BY_DA.get(
                            next_turn.get("da", ""),
                            "Answer from the document context, stay grounded, and keep the response concise."
                        )
                        examples.append(
                            {
                                "question": current_turn.get("utterance", "").strip(),
                                "answer_style": style_hint,
                                "dialogue_act": next_turn.get("da", ""),
                                "domain": domain,
                                "source_doc_id": doc_id,
                                "source_title": doc_title,
                                "agent_response_example": next_turn.get("utterance", "").strip(),
                                "retrieval_hint": f"Ground on document '{doc_title}' in the {domain} domain.",
                                "split": split,
                            }
                        )

    # Keep a compact but varied runtime artifact.
    deduped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for item in examples:
        key = (item["question"], item["dialogue_act"], item["source_doc_id"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= 250:
            break

    _write_json(output, deduped)
    return deduped


def prepare_doc2dial_behavior_artifacts(
    source_examples: list[dict] | None = None,
    raw_dir: Path = DOC2DIAL_RAW_DIR,
    output: Path = DOC2DIAL_BEHAVIOR_FILE,
) -> list[dict]:
    examples = source_examples if source_examples is not None else prepare_doc2dial_artifacts(raw_dir=raw_dir)
    behaviors: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for example in examples:
        behavior_type = DOC2DIAL_BEHAVIOR_BY_DA.get(example["dialogue_act"], "grounded_answer")
        key = (example["question"], behavior_type, example["source_doc_id"])
        if key in seen:
            continue
        seen.add(key)
        behaviors.append(
            {
                "question": example["question"],
                "behavior_type": behavior_type,
                "grounded_instruction": example["answer_style"],
                "dialogue_act": example["dialogue_act"],
                "source_doc_id": example["source_doc_id"],
                "source_title": example["source_title"],
                "response_example": example["agent_response_example"],
                "evaluation_hint": (
                    "Must stay grounded in firm documents and clearly say when support is unavailable."
                    if behavior_type == "unsupported"
                    else "Must answer from retrieved firm-document evidence and stay concise."
                ),
            }
        )
        if len(behaviors) >= 180:
            break

    _write_json(output, behaviors)
    return behaviors


def write_source_metadata(
    oulad_records: list[dict],
    oulad_training_records: list[dict],
    doc2dial_records: list[dict],
    oulad_splits: dict | None = None,
    doc2dial_behaviors: list[dict] | None = None,
    output: Path = SOURCES_METADATA_FILE,
) -> dict:
    split_payload = oulad_splits or {}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "oulad": {
                "raw_dir": str(OULAD_RAW_DIR),
                "profile_file": str(OULAD_FILE),
                "profile_record_count": len(oulad_records),
                "training_file": str(OULAD_TRAINING_FILE),
                "training_record_count": len(oulad_training_records),
                "splits_file": str(OULAD_SPLITS_FILE),
                "split_counts": split_payload.get("counts", {}),
                "training_outlier_handling": {
                    "method": "winsorized_quantile_clip",
                    "low_quantile": OUTLIER_LOW_QUANTILE,
                    "high_quantile": OUTLIER_HIGH_QUANTILE,
                },
            },
            "doc2dial": {
                "raw_dir": str(DOC2DIAL_RAW_DIR),
                "processed_file": str(DOC2DIAL_FILE),
                "record_count": len(doc2dial_records),
                "behavior_file": str(DOC2DIAL_BEHAVIOR_FILE),
                "behavior_record_count": len(doc2dial_behaviors or []),
            },
        },
    }
    _write_json(output, payload)
    return payload


def build_firm_learning_profiles(source: Path = OULAD_RAW_DIR, output: Path = OULAD_FILE) -> list[dict]:
    return prepare_oulad_artifacts(raw_dir=source, output=output)


def build_oulad_training_examples(
    source: Path = OULAD_RAW_DIR,
    output: Path = OULAD_TRAINING_FILE,
) -> list[dict]:
    return prepare_oulad_training_artifacts(raw_dir=source, output=output)


def build_doc2dial_behaviors(
    source: Path = DOC2DIAL_RAW_DIR,
    output: Path = DOC2DIAL_BEHAVIOR_FILE,
) -> list[dict]:
    return prepare_doc2dial_behavior_artifacts(raw_dir=source, output=output)
