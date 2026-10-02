"""The project licence: the copy in `backend/` equals the canonical text at the root."""

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_license_copy_matches_the_repository_license() -> None:
    canonical = (BACKEND.parent / "LICENSE").read_text(encoding="utf-8")

    assert (BACKEND / "LICENSE").read_text(encoding="utf-8") == canonical
