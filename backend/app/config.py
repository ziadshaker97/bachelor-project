import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        os.environ.setdefault(key, value)


BASE_DIR = Path(__file__).resolve().parent.parent
_load_env_file(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
SEED_DIR = DATA_DIR / "seed"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
DEFAULT_RUNTIME_ROOT = Path(os.getenv("LOCALAPPDATA", str(DATA_DIR))) / "employee-onboarding-intelligence" / "runtime"
RUNTIME_DIR = Path(os.getenv("EOI_RUNTIME_DIR", str(DEFAULT_RUNTIME_ROOT)))
DOCS_DIR = SEED_DIR / "documents"
MODULES_FILE = SEED_DIR / "training_modules.json"
COURSES_FILE = SEED_DIR / "courses_catalog.json"
EMPLOYEE_DIRECTORY_FILE = SEED_DIR / "employee_directory.json"
ROADMAP_FILE = SEED_DIR / "onboarding_roadmaps.json"
HISTORICAL_PROGRESS_FILE = SEED_DIR / "historical_progress.json"
OULAD_RAW_DIR = RAW_DIR / "oulad" / "extracted"
DOC2DIAL_RAW_DIR = RAW_DIR / "doc2dial" / "extracted"
OULAD_FILE = PROCESSED_DIR / "oulad_profiles.json"
OULAD_TRAINING_FILE = PROCESSED_DIR / "oulad_training_examples.json"
OULAD_SPLITS_FILE = PROCESSED_DIR / "oulad_splits.json"
DOC2DIAL_FILE = PROCESSED_DIR / "doc2dial_examples.json"
DOC2DIAL_BEHAVIOR_FILE = PROCESSED_DIR / "doc2dial_behaviors.json"
SOURCES_METADATA_FILE = PROCESSED_DIR / "sources.json"
SUCCESS_MODEL_FILE = MODELS_DIR / "oulad_success_model.json"
RECOMMENDATION_MODEL_FILE = MODELS_DIR / "oulad_recommendation_model.json"
TRAINING_REPORT_FILE = MODELS_DIR / "oulad_training_report.json"
DB_PATH = RUNTIME_DIR / "app.db"

LLM_BACKEND = os.getenv("LLM_BACKEND", "extractive")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30"))
TOP_K_DOCS = int(os.getenv("TOP_K_DOCS", "3"))
EXTERNAL_COURSE_PROVIDER = os.getenv("EXTERNAL_COURSE_PROVIDER", "linkedin_learning")
LINKEDIN_LEARNING_CLIENT_ID = os.getenv("LINKEDIN_LEARNING_CLIENT_ID", "")
LINKEDIN_LEARNING_CLIENT_SECRET = os.getenv("LINKEDIN_LEARNING_CLIENT_SECRET", "")
LINKEDIN_LEARNING_TOKEN_URL = os.getenv("LINKEDIN_LEARNING_TOKEN_URL", "https://www.linkedin.com/oauth/v2/accessToken")
LINKEDIN_LEARNING_API_BASE = os.getenv("LINKEDIN_LEARNING_API_BASE", "https://api.linkedin.com/v2")
LINKEDIN_LEARNING_LOCALE_LANGUAGE = os.getenv("LINKEDIN_LEARNING_LOCALE_LANGUAGE", "en")
LINKEDIN_LEARNING_LOCALE_COUNTRY = os.getenv("LINKEDIN_LEARNING_LOCALE_COUNTRY", "US")
LINKEDIN_LEARNING_LICENSED_ONLY = os.getenv("LINKEDIN_LEARNING_LICENSED_ONLY", "true").lower() == "true"

OULAD_ARCHIVE_URL = "https://cdn.uci-ics-mlr-prod.aws.uci.edu/349/open%2Buniversity%2Blearning%2Banalytics%2Bdataset.zip"
DOC2DIAL_ARCHIVE_URL = "https://doc2dial.github.io/file/doc2dial_v1.0.1.zip"
