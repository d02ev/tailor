"""
Temporary resume review checkpoint utilities.
"""

from __future__ import annotations

import json
from pathlib import Path


def _assets_dir() -> Path:
    """
    Returns the project-local assets directory and ensures it exists.
    """
    assets = Path(__file__).resolve().parents[1] / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    return assets


def get_review_file_path() -> Path:
    """
    Returns the project-local path used for the editable final resume checkpoint.
    """
    return _assets_dir() / "resume.json"


def write_review_file(final_resume: dict) -> Path:
    """
    Writes the final resume to project-local storage for manual review/editing.
    """
    review_path = get_review_file_path()
    review_path.write_text(json.dumps(final_resume, indent=2), encoding="utf-8")
    return review_path


def load_reviewed_resume(review_path: Path) -> dict:
    """
    Loads the user-edited resume JSON and validates it is a JSON object.
    """
    content = review_path.read_text(encoding="utf-8")
    parsed = json.loads(content)

    if not isinstance(parsed, dict):
        raise ValueError("resume.json must contain a JSON object at the top level.")

    return parsed


def cleanup_review_file(review_path: Path) -> None:
    """
    Removes the temp review file if present.
    """
    review_path.unlink(missing_ok=True)
