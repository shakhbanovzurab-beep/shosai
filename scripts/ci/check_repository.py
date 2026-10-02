"""Stack-independent repository checks: file length and secrets in git.

The rules are in `.claude/CLAUDE.md` (the Architecture and Security sections). The script
looks only at files tracked by git, so `node_modules/`, `.venv/` and other ignored
directories are not checked.

Run from the repository root: `python3 scripts/ci/check_repository.py`.
Exit code 1 means violations were found, 0 means everything is clean.
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class LengthLimit:
    """Line limit for the source files of one zone."""

    zone: str
    suffixes: frozenset[str]
    max_lines: int


LENGTH_LIMITS = (
    LengthLimit("backend", frozenset({".py"}), 300),
    LengthLimit(
        "frontend",
        frozenset({".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".css"}),
        200,
    ),
    # Стенд визуального паритета (D2): TypeScript — по лимиту фронтенда,
    # засев черновика на Python — по лимиту бэкенда.
    LengthLimit("parity", frozenset({".ts", ".js", ".mjs"}), 200),
    LengthLimit("parity", frozenset({".py"}), 300),
)

# Сгенерированный код под лимит не попадает: каталоги генераторов и миграции Alembic.
GENERATED_DIRECTORIES = frozenset({"generated", "__generated__"})
MIGRATION_DIRECTORIES = (("alembic", "versions"), ("migrations", "versions"))
GENERATED_MARKER = "@generated"
MARKER_SEARCH_LINES = 5

ALLOWED_ENV_FILES = frozenset({".env.example"})


def tracked_files() -> list[PurePosixPath]:
    """Returns the paths of all files tracked by git."""
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout
    return [PurePosixPath(raw.decode()) for raw in output.split(b"\0") if raw]


def is_generated(path: PurePosixPath, lines: list[str]) -> bool:
    """The file is generated: it is in a generator directory, is a migration or has the marker."""
    parts = path.parts
    if GENERATED_DIRECTORIES.intersection(parts):
        return True
    for pair in MIGRATION_DIRECTORIES:
        if any(parts[i : i + 2] == pair for i in range(len(parts) - 1)):
            return True
    return any(GENERATED_MARKER in line for line in lines[:MARKER_SEARCH_LINES])


def length_violation(path: PurePosixPath) -> str | None:
    """Returns a description of the line limit violation, or None."""
    for limit in LENGTH_LIMITS:
        if path.parts[0] != limit.zone or path.suffix not in limit.suffixes:
            continue
        with open(path, encoding="utf-8", errors="replace") as source:
            lines = source.readlines()
        if len(lines) > limit.max_lines and not is_generated(path, lines):
            return f"{path}: {len(lines)} lines, limit for {limit.zone}/ is {limit.max_lines}"
    return None


def env_violation(path: PurePosixPath) -> str | None:
    """Returns a description of the violation if an environment file got into git."""
    name = path.name
    is_env_file = name == ".env" or name.startswith(".env.")
    if is_env_file and name not in ALLOWED_ENV_FILES:
        return f"{path}: environment file is tracked by git; secrets live only in the environment"
    return None


def main() -> int:
    """Checks all tracked files and prints the violations in the GitHub Actions format."""
    violations: list[str] = []
    for path in tracked_files():
        for check in (env_violation, length_violation):
            violation = check(path)
            if violation is not None:
                violations.append(violation)
    for violation in violations:
        print(f"::error::{violation}")
    if violations:
        print(f"{len(violations)} violation(s) found.")
        return 1
    print("Repository checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
