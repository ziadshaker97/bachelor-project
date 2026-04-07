from __future__ import annotations

import json
import urllib.request
import zipfile
from pathlib import Path


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def download_file(url: str, destination: Path) -> Path:
    ensure_dir(destination.parent)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    urllib.request.urlretrieve(url, destination)
    return destination


def extract_zip(archive: Path, destination: Path) -> Path:
    ensure_dir(destination)
    with zipfile.ZipFile(archive, "r") as handle:
        handle.extractall(destination)
    return destination


def write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

