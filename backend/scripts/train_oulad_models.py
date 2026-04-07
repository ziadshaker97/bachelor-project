from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import RECOMMENDATION_MODEL_FILE, TRAINING_REPORT_FILE
from app.services.recommender_model import train_recommendation_ranker
from app.services.training import train_oulad_models


def main() -> None:
    diagnostics_report = train_oulad_models()
    recommendation_artifact = train_recommendation_ranker()

    report = json.loads(TRAINING_REPORT_FILE.read_text(encoding="utf-8"))
    report["models"]["recommendation_ranker"] = {
        "path": str(RECOMMENDATION_MODEL_FILE),
        "model_type": recommendation_artifact["model_type"],
        "target": recommendation_artifact["target"],
        "skill_gap_target": recommendation_artifact["skill_gap_target"],
        "metrics": recommendation_artifact["metrics"],
        "heuristic_comparison": recommendation_artifact["metrics"]["test"]["heuristic_baseline"],
    }
    TRAINING_REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Trained success classifier -> {diagnostics_report['models']['success_classifier']['path']}")
    print(f"Trained recommendation ranker -> {report['models']['recommendation_ranker']['path']}")
    print(f"Wrote training report -> {TRAINING_REPORT_FILE}")


if __name__ == "__main__":
    main()
