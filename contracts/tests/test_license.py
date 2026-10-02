"""The project license: the copy in `contracts/` matches the canonical text at the root."""

from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1]


def test_license_copy_matches_the_repository_license() -> None:
    canonical = (CONTRACTS.parent / "LICENSE").read_text(encoding="utf-8")
    assert (CONTRACTS / "LICENSE").read_text(encoding="utf-8") == canonical
