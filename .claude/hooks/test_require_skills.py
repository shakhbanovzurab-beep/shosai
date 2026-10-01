"""Тесты хука require_skills: что блокируется без скиллов, а что — нет."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).with_name("require_skills.py")
PROJECT = HOOK.parents[2].resolve()
DRAFT = Path("/root/whisperer")
BACKEND_SKILLS = ("fastapi", "python-doctor")

BLOCKED_WITHOUT_SKILLS = [
    ("Bash", "cd backend && uv run pytest"),
    ("Bash", "cd backend && uv run mypy ."),
    ("Bash", "sed -i 's/a/b/' backend/x.py"),
    ("Bash", "cat > frontend/src/x.tsx <<'X'\nhi\nX"),
    ("Bash", "cd frontend && npm run doctor -- --score"),
    ("Bash", "docker compose -f compose.dev.yaml up -d"),
    ("Bash", "docker system prune -a"),
    ("Bash", "git add backend/app.py && git commit -m x"),
    ("Bash", "mkdir -p frontend/src"),
    ("Bash", f"mkdir -p {PROJECT}/frontend/probe"),
    ("Bash", f"cp /tmp/a.py {PROJECT}/backend/app/a.py"),
    ("Bash", f"cat >{PROJECT}/frontend/x.ts <<'X'\nhi\nX"),
    ("Bash", f"python3 - <<'X'\nopen('{PROJECT}/backend/a.py','w').write('x')\nX"),
    ("Bash", f"cp {DRAFT}/docker-compose.prod.yml {PROJECT}/compose.prod.yaml"),
    ("Bash", f"rm -rf {PROJECT}/frontend"),
    ("Edit", f"{PROJECT}/backend/app/main.py"),
    ("Write", f"{PROJECT}/compose.dev.yaml"),
    ("Write", f"{PROJECT}/backend/Dockerfile"),
]

ALLOWED_WITHOUT_SKILLS = [
    ("Bash", "ls backend && cat backend/app.py"),
    ("Bash", "git status && git diff backend/"),
    ("Bash", "grep -rn foo frontend/src | head"),
    ("Bash", "sed -n 1,5p backend/x.py"),
    ("Bash", "echo hi 2>/dev/null"),
    ("Bash", "docker ps -a"),
    ("Bash", "docker compose ps"),
    ("Bash", f"ls {DRAFT}/backend && grep -rn x {DRAFT}/backend/src"),
    ("Bash", f"cd {DRAFT}/backend && uv run python -c 'print(1)'"),
    ("Bash", f"cp {DRAFT}/docker-compose.prod.yml /tmp/x.yml"),
    ("Bash", "python3 scripts/ci/check_repository.py"),
    ("Bash", "cat > /tmp/notes.md <<'X'\nsee backend/ and frontend/\nX"),
    ("Bash", "git commit -q .claude/CLAUDE.md -F - <<'X'\nTouch backend/ docs\nX"),
    ("Bash", "mypy --strict .claude/hooks/require_skills.py"),
    ("Bash", f"ls -la {PROJECT}/frontend"),
    ("Write", f"{PROJECT}/docs/plan/STATUS.md"),
    ("Write", f"{DRAFT}/backend/x.py"),
]


def write_transcript(directory: Path, skills: tuple[str, ...]) -> Path:
    """Транскрипт сессии, в которой загружены указанные скиллы."""
    content = [{"type": "tool_use", "name": "Skill", "input": {"skill": skill}} for skill in skills]
    path = directory / "transcript.jsonl"
    path.write_text(json.dumps({"message": {"content": content or "no skills"}}) + "\n", encoding="utf-8")
    return path


def run_hook(tool: str, argument: str, transcript: Path | None) -> int:
    """Запускает хук так же, как Claude Code, и возвращает код выхода."""
    tool_input = {"command": argument} if tool == "Bash" else {"file_path": argument}
    payload = {"tool_name": tool, "cwd": str(PROJECT), "tool_input": tool_input}
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(PROJECT)},
        check=False,
    )
    return result.returncode


@pytest.mark.parametrize(("tool", "argument"), BLOCKED_WITHOUT_SKILLS)
def test_blocks_zone_action_without_skills(tmp_path: Path, tool: str, argument: str) -> None:
    assert run_hook(tool, argument, write_transcript(tmp_path, ())) == 2


@pytest.mark.parametrize(("tool", "argument"), ALLOWED_WITHOUT_SKILLS)
def test_allows_reads_and_actions_outside_zones(tmp_path: Path, tool: str, argument: str) -> None:
    assert run_hook(tool, argument, write_transcript(tmp_path, ())) == 0


def test_allows_backend_work_once_skills_are_loaded(tmp_path: Path) -> None:
    transcript = write_transcript(tmp_path, BACKEND_SKILLS)
    assert run_hook("Bash", "cd backend && uv run python-doctor . --score", transcript) == 0
    assert run_hook("Edit", f"{PROJECT}/backend/app/main.py", transcript) == 0


def test_partial_frontend_skills_still_block(tmp_path: Path) -> None:
    transcript = write_transcript(tmp_path, ("vercel-react-best-practices",))
    assert run_hook("Write", f"{PROJECT}/frontend/src/App.tsx", transcript) == 2


def test_fails_open_without_transcript() -> None:
    assert run_hook("Edit", f"{PROJECT}/backend/app/main.py", None) == 0
