import json

from .config import (
    COURSES_FILE,
    DOC2DIAL_BEHAVIOR_FILE,
    DOC2DIAL_FILE,
    DOCS_DIR,
    EMPLOYEE_DIRECTORY_FILE,
    HISTORICAL_PROGRESS_FILE,
    MODULES_FILE,
    OULAD_FILE,
    OULAD_SPLITS_FILE,
    OULAD_TRAINING_FILE,
    ROADMAP_FILE,
)
from .models import CourseRecord, DocumentRecord, EmployeeProfile, RoadmapMilestone, TrainingModule


def _read_json(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Required processed dataset artifact not found: {path}. "
            "Run the dataset preparation scripts in backend/scripts first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_modules() -> list[TrainingModule]:
    return [TrainingModule(**item) for item in json.loads(MODULES_FILE.read_text(encoding="utf-8"))]


def load_courses() -> list[CourseRecord]:
    return [CourseRecord(**item) for item in json.loads(COURSES_FILE.read_text(encoding="utf-8"))]


def load_seed_profiles() -> list[EmployeeProfile]:
    return [EmployeeProfile(**item) for item in json.loads(EMPLOYEE_DIRECTORY_FILE.read_text(encoding="utf-8"))]


def load_historical_progress() -> list[dict]:
    return json.loads(HISTORICAL_PROGRESS_FILE.read_text(encoding="utf-8"))


def load_roadmaps() -> dict[str, list[RoadmapMilestone]]:
    raw = json.loads(ROADMAP_FILE.read_text(encoding="utf-8"))
    return {
        role: [RoadmapMilestone(**item) for item in milestones]
        for role, milestones in raw.items()
    }


def load_oulad_profiles() -> list[dict]:
    return _read_json(OULAD_FILE)


def load_oulad_training_examples() -> list[dict]:
    return _read_json(OULAD_TRAINING_FILE)


def load_oulad_splits() -> dict:
    return _read_json(OULAD_SPLITS_FILE)


def load_doc2dial_examples() -> list[dict]:
    return _read_json(DOC2DIAL_FILE)


def load_doc2dial_behaviors() -> list[dict]:
    return _read_json(DOC2DIAL_BEHAVIOR_FILE)


def load_documents() -> list[DocumentRecord]:
    documents: list[DocumentRecord] = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        title = lines[0].replace("# ", "").strip() if lines else path.stem
        category = path.stem.split("_", 1)[0]
        documents.append(
            DocumentRecord(
                document_id=path.stem,
                title=title,
                category=category,
                content=raw,
            )
        )
    return documents
