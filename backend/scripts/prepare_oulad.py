from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import OULAD_ARCHIVE_URL, RAW_DIR
from app.services.preprocessing import prepare_oulad_artifacts, prepare_oulad_training_artifacts
from scripts._common import download_file, extract_zip


def main() -> None:
    raw_dir = RAW_DIR / "oulad"
    archive = raw_dir / "oulad.zip"
    extracted = raw_dir / "extracted"
    download_file(OULAD_ARCHIVE_URL, archive)
    extract_zip(archive, extracted)
    records = prepare_oulad_artifacts(raw_dir=extracted)
    training_records = prepare_oulad_training_artifacts(raw_dir=extracted)
    print(f"Prepared {len(records)} OULAD-derived role profiles.")
    print(f"Prepared {len(training_records)} OULAD training examples.")


if __name__ == "__main__":
    main()
