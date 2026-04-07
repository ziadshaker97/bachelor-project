from pathlib import Path

from app.services.preprocessing import (
    OUTLIER_HIGH_QUANTILE,
    OUTLIER_LOW_QUANTILE,
    _clip_training_feature_outliers,
    build_oulad_split_artifact,
    prepare_doc2dial_behavior_artifacts,
    prepare_oulad_training_artifacts,
    write_source_metadata,
)


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def test_prepare_oulad_training_artifacts_builds_features_and_labels(tmp_path: Path) -> None:
    raw_dir = tmp_path / "oulad"
    raw_dir.mkdir(parents=True)

    _write_csv(
        raw_dir / "courses.csv",
        """
code_module,code_presentation,module_presentation_length
AAA,2013J,100
""",
    )
    _write_csv(
        raw_dir / "assessments.csv",
        """
code_module,code_presentation,id_assessment,assessment_type,date,weight
AAA,2013J,101,TMA,10,40
AAA,2013J,102,Exam,70,60
""",
    )
    _write_csv(
        raw_dir / "studentAssessment.csv",
        """
id_assessment,id_student,date_submitted,is_banked,score
101,1,12,0,80
102,1,75,0,90
101,2,8,1,50
""",
    )
    _write_csv(
        raw_dir / "studentInfo.csv",
        """
code_module,code_presentation,id_student,gender,region,highest_education,imd_band,age_band,num_of_prev_attempts,studied_credits,disability,final_result
AAA,2013J,1,M,Region A,HE Qualification,80-90%,35-55,1,60,N,Pass
AAA,2013J,2,F,Region B,A Level or Equivalent,20-30%,0-35,0,120,Y,Withdrawn
""",
    )
    _write_csv(
        raw_dir / "studentRegistration.csv",
        """
code_module,code_presentation,id_student,date_registration,date_unregistration
AAA,2013J,1,-20,?
AAA,2013J,2,5,30
""",
    )
    _write_csv(
        raw_dir / "studentVle.csv",
        """
code_module,code_presentation,id_student,id_site,date,sum_click
AAA,2013J,1,500,0,10
AAA,2013J,1,501,20,5
AAA,2013J,2,500,-3,7
AAA,2013J,2,501,40,3
""",
    )
    _write_csv(
        raw_dir / "vle.csv",
        """
id_site,code_module,code_presentation,activity_type,week_from,week_to
500,AAA,2013J,resource,?,
501,AAA,2013J,quiz,?,
""",
    )

    output = tmp_path / "oulad_training_examples.json"
    examples = prepare_oulad_training_artifacts(raw_dir=raw_dir, output=output)
    split_output = tmp_path / "oulad_splits.json"

    assert output.exists()
    assert split_output.exists()
    assert len(examples) == 2

    pass_example = next(item for item in examples if item["student_id"] == "1")
    pass_features = pass_example["features"]
    assert pass_features["days_registered_before_start"] == 20
    assert pass_features["registered_late"] == 0
    assert pass_features["unregistered"] == 0
    assert pass_features["total_vle_clicks"] == 15
    assert pass_features["early_vle_clicks"] == 15
    assert pass_features["clicks_resource"] == 10
    assert pass_features["early_clicks_quiz"] == 5
    assert pass_features["assessments_submitted"] == 2
    assert pass_features["late_assessment_submissions"] == 2
    assert pass_features["assessment_score_mean"] == 85.0
    assert pass_features["assessment_score_weighted_mean"] == 86.0
    assert pass_features["early_assessment_score_mean"] == 80.0
    assert pass_features["tma_score_mean"] == 80.0
    assert pass_features["exam_score_mean"] == 90.0

    pass_labels = pass_example["labels"]
    assert pass_labels["final_result"] == "Pass"
    assert pass_labels["completed"] == 1
    assert pass_labels["success"] == 1
    assert pass_labels["withdrawn"] == 0
    assert pass_labels["recommendation_score"] == 0.8
    assert pass_labels["next_best_module"]
    assert pass_labels["skill_gap"]
    assert pass_example["split"] in {"train", "validation", "test"}

    withdrawn_example = next(item for item in examples if item["student_id"] == "2")
    withdrawn_features = withdrawn_example["features"]
    assert withdrawn_features["registered_late"] == 1
    assert withdrawn_features["unregistered"] == 1
    assert withdrawn_features["days_until_unregistration"] == 30
    assert withdrawn_features["prestart_vle_clicks"] == 7
    assert withdrawn_features["early_vle_clicks"] == 7
    assert withdrawn_features["assessment_score_mean"] == 50.0
    assert withdrawn_features["assessments_banked"] == 1

    withdrawn_labels = withdrawn_example["labels"]
    assert withdrawn_labels["completed"] == 0
    assert withdrawn_labels["success"] == 0
    assert withdrawn_labels["withdrawn"] == 1
    assert withdrawn_labels["recommendation_score"] == 0.0


def test_write_source_metadata_tracks_training_artifact_counts(tmp_path: Path) -> None:
    output = tmp_path / "sources.json"
    metadata = write_source_metadata(
        oulad_records=[{"role": "Software Engineer"}],
        oulad_training_records=[{"example_id": "AAA_2013J_1"}, {"example_id": "AAA_2013J_2"}],
        doc2dial_records=[{"question": "How do I reset my password?"}],
        oulad_splits={"counts": {"train": 1, "validation": 1, "test": 0}},
        doc2dial_behaviors=[{"behavior_type": "grounded_answer"}],
        output=output,
    )

    assert output.exists()
    assert metadata["sources"]["oulad"]["profile_record_count"] == 1
    assert metadata["sources"]["oulad"]["training_record_count"] == 2
    assert metadata["sources"]["oulad"]["split_counts"]["validation"] == 1
    assert metadata["sources"]["oulad"]["training_outlier_handling"]["method"] == "winsorized_quantile_clip"
    assert metadata["sources"]["doc2dial"]["record_count"] == 1
    assert metadata["sources"]["doc2dial"]["behavior_record_count"] == 1


def test_clip_training_feature_outliers_caps_extreme_numeric_values() -> None:
    examples = [
        {
            "example_id": f"ex-{index}",
            "features": {
                "total_vle_clicks": 10,
                "clicks_resource": 5,
                "assessment_score_mean": 70.0,
                "gender": "M",
            },
            "labels": {"success": 1},
        }
        for index in range(99)
    ]
    examples.append(
        {
            "example_id": "ex-outlier",
            "features": {
                "total_vle_clicks": 10000,
                "clicks_resource": 9000,
                "assessment_score_mean": 70.0,
                "gender": "F",
            },
            "labels": {"success": 0},
        }
    )

    bounds = _clip_training_feature_outliers(examples)

    assert bounds["total_vle_clicks"]["lower_bound"] == 10.0
    assert bounds["clicks_resource"]["lower_bound"] == 5.0
    assert bounds["total_vle_clicks"]["upper_bound"] < 10000
    assert bounds["clicks_resource"]["upper_bound"] < 9000
    assert examples[-1]["features"]["total_vle_clicks"] == round(bounds["total_vle_clicks"]["upper_bound"])
    assert examples[-1]["features"]["clicks_resource"] == round(bounds["clicks_resource"]["upper_bound"])
    assert examples[-1]["features"]["assessment_score_mean"] == 70.0
    assert OUTLIER_LOW_QUANTILE == 0.01
    assert OUTLIER_HIGH_QUANTILE == 0.99


def test_build_oulad_split_artifact_is_deterministic(tmp_path: Path) -> None:
    examples = [{"example_id": "AAA_2013J_1", "features": {}, "labels": {}}]
    first = build_oulad_split_artifact(examples, output=tmp_path / "splits-a.json")
    second = build_oulad_split_artifact(examples, output=tmp_path / "splits-b.json")
    assert first["assignments"] == second["assignments"]
    assert first["assignments"][0]["split"] in {"train", "validation", "test"}


def test_prepare_doc2dial_behavior_artifacts_derives_behavior_types(tmp_path: Path) -> None:
    output = tmp_path / "doc2dial_behaviors.json"
    records = prepare_doc2dial_behavior_artifacts(
        source_examples=[
            {
                "question": "Can I get help with this form?",
                "answer_style": "Answer from the grounded context.",
                "dialogue_act": "respond_solution",
                "source_doc_id": "doc-1",
                "source_title": "Benefits form",
                "agent_response_example": "Use the benefits form instructions.",
            },
            {
                "question": "Does this apply to me?",
                "answer_style": "Clarify the condition first.",
                "dialogue_act": "query_condition",
                "source_doc_id": "doc-2",
                "source_title": "Leave policy",
                "agent_response_example": "Can you confirm your employment type?",
            },
        ],
        output=output,
    )
    assert output.exists()
    assert {item["behavior_type"] for item in records} == {"grounded_answer", "clarifying_follow_up"}
