from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models import EmployeeProfile
from app.seed import load_doc2dial_behaviors
from app.services.llm import ExtractiveAdapter
from app.services.retrieval import RetrievalService


def main() -> None:
    retrieval = RetrievalService()
    adapter = ExtractiveAdapter()
    profile = EmployeeProfile(
        employee_id="eval-user",
        role="Product Manager",
        department="Product",
        experience_level="intermediate",
        known_skills=["communication"],
        learning_preferences=["workshop", "text"],
    )

    behaviors = load_doc2dial_behaviors()
    sample = behaviors[:60]
    grounded = 0
    unsupported = 0
    follow_up = 0
    evaluated = 0

    for item in sample:
        message = item["question"]
        history = [{"speaker": "user", "message": "Can you help me with onboarding paperwork?"}] if item["behavior_type"] == "clarifying_follow_up" else []
        sources = retrieval.retrieve(message)
        answer = adapter.generate(profile=profile, message=message, history=history, sources=sources)
        evaluated += 1
        if item["behavior_type"] == "grounded_answer" and sources and any(source.title.lower() in answer.lower() for source in sources[:1]):
            grounded += 1
        if item["behavior_type"] == "unsupported" and ("could not find" in answer.lower() or "not supported" in answer.lower()):
            unsupported += 1
        if item["behavior_type"] == "clarifying_follow_up" and ("earlier" in answer.lower() or "follow" in answer.lower() or "exact" in answer.lower()):
            follow_up += 1

    payload = {
        "evaluated_examples": evaluated,
        "grounded_answer_rate": round(grounded / max(1, sum(1 for item in sample if item["behavior_type"] == "grounded_answer")), 4),
        "unsupported_handling_rate": round(unsupported / max(1, sum(1 for item in sample if item["behavior_type"] == "unsupported")), 4),
        "follow_up_handling_rate": round(follow_up / max(1, sum(1 for item in sample if item["behavior_type"] == "clarifying_follow_up")), 4),
        "knowledge_source": "firm_documents_rag_only",
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
