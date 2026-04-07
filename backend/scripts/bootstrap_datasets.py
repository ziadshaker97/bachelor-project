from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import DOC2DIAL_ARCHIVE_URL, OULAD_ARCHIVE_URL, OULAD_SPLITS_FILE, RAW_DIR
from app.services.preprocessing import (
    prepare_doc2dial_artifacts,
    prepare_doc2dial_behavior_artifacts,
    prepare_oulad_artifacts,
    prepare_oulad_training_artifacts,
    write_source_metadata,
)
from scripts._common import download_file, extract_zip


def main() -> None:
    oulad_archive = RAW_DIR / "oulad" / "oulad.zip"
    oulad_extracted = RAW_DIR / "oulad" / "extracted"
    doc2dial_archive = RAW_DIR / "doc2dial" / "doc2dial_v1.0.1.zip"
    doc2dial_extracted = RAW_DIR / "doc2dial" / "extracted"

    download_file(OULAD_ARCHIVE_URL, oulad_archive)
    extract_zip(oulad_archive, oulad_extracted)
    download_file(DOC2DIAL_ARCHIVE_URL, doc2dial_archive)
    extract_zip(doc2dial_archive, doc2dial_extracted)

    oulad_records = prepare_oulad_artifacts(raw_dir=oulad_extracted)
    oulad_training_records = prepare_oulad_training_artifacts(raw_dir=oulad_extracted)
    oulad_splits = json.loads(OULAD_SPLITS_FILE.read_text(encoding="utf-8"))
    doc2dial_records = prepare_doc2dial_artifacts(raw_dir=doc2dial_extracted)
    doc2dial_behaviors = prepare_doc2dial_behavior_artifacts(source_examples=doc2dial_records, raw_dir=doc2dial_extracted)
    metadata = write_source_metadata(
        oulad_records,
        oulad_training_records,
        doc2dial_records,
        oulad_splits=oulad_splits,
        doc2dial_behaviors=doc2dial_behaviors,
    )

    print(f"Prepared {len(oulad_records)} OULAD profiles.")
    print(f"Prepared {len(oulad_training_records)} OULAD training examples.")
    print(f"Prepared {len(doc2dial_records)} Doc2Dial examples.")
    print(f"Prepared {len(doc2dial_behaviors)} Doc2Dial behavior examples.")
    print(f"Wrote source metadata to {metadata['sources']['oulad']['profile_file']} and related files.")


if __name__ == "__main__":
    main()
