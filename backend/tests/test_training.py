import json
from pathlib import Path

from app.services.training import train_oulad_models


def test_train_oulad_models_writes_two_artifacts_and_report(tmp_path: Path) -> None:
    dataset = [
        {
            "example_id": "AAA_2013J_1",
            "features": {
                "gender": "M",
                "region": "A",
                "studied_credits": 60,
                "total_vle_clicks": 100,
                "assessment_score_mean": 75.0,
            },
            "labels": {
                "success": 1,
                "recommendation_score": 0.8,
            },
        },
        {
            "example_id": "AAA_2013J_2",
            "features": {
                "gender": "F",
                "region": "B",
                "studied_credits": 30,
                "total_vle_clicks": 10,
                "assessment_score_mean": 40.0,
            },
            "labels": {
                "success": 0,
                "recommendation_score": 0.0,
            },
        },
        {
            "example_id": "BBB_2014J_3",
            "features": {
                "gender": "M",
                "region": "A",
                "studied_credits": 90,
                "total_vle_clicks": 140,
                "assessment_score_mean": 88.0,
            },
            "labels": {
                "success": 1,
                "recommendation_score": 1.0,
            },
        },
        {
            "example_id": "BBB_2014J_4",
            "features": {
                "gender": "F",
                "region": "C",
                "studied_credits": 20,
                "total_vle_clicks": 5,
                "assessment_score_mean": 25.0,
            },
            "labels": {
                "success": 0,
                "recommendation_score": 0.0,
            },
        },
    ]

    dataset_path = tmp_path / "dataset.json"
    success_model_path = tmp_path / "success_model.json"
    recommendation_model_path = tmp_path / "recommendation_model.json"
    report_path = tmp_path / "report.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    report = train_oulad_models(
        dataset_path=dataset_path,
        success_model_path=success_model_path,
        recommendation_model_path=recommendation_model_path,
        report_path=report_path,
    )

    assert success_model_path.exists()
    assert recommendation_model_path.exists()
    assert report_path.exists()
    assert report["models"]["success_classifier"]["target"] == "success"
    assert report["models"]["recommendation_regressor"]["target"] == "recommendation_score"

    success_payload = json.loads(success_model_path.read_text(encoding="utf-8"))
    recommendation_payload = json.loads(recommendation_model_path.read_text(encoding="utf-8"))
    assert success_payload["model_type"] == "logistic_regression_sgd"
    assert recommendation_payload["model_type"] == "linear_regression_sgd"
    assert success_payload["metrics"]["test"]["accuracy"] >= 0.0
    assert recommendation_payload["metrics"]["test"]["rmse"] >= 0.0
