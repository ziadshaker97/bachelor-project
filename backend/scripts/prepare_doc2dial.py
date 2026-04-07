from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import DOC2DIAL_ARCHIVE_URL, RAW_DIR
from app.services.preprocessing import prepare_doc2dial_artifacts, prepare_doc2dial_behavior_artifacts
from scripts._common import download_file, extract_zip


def main() -> None:
    raw_dir = RAW_DIR / "doc2dial"
    archive = raw_dir / "doc2dial_v1.0.1.zip"
    extracted = raw_dir / "extracted"
    download_file(DOC2DIAL_ARCHIVE_URL, archive)
    extract_zip(archive, extracted)
    records = prepare_doc2dial_artifacts(raw_dir=extracted)
    behavior_records = prepare_doc2dial_behavior_artifacts(source_examples=records, raw_dir=extracted)
    print(f"Prepared {len(records)} Doc2Dial-derived chat examples.")
    print(f"Prepared {len(behavior_records)} Doc2Dial behavior examples.")


if __name__ == "__main__":
    main()
