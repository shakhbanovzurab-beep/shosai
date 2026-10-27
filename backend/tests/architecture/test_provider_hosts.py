"""Provider hosts appear only in the port (ADR 0034 point 3).

The import contract cannot see a raw HTTP call to a provider made with a client the slice is
allowed to import; the provider's host name in the source can.
"""

from pathlib import Path
from typing import Final

SOURCE: Final = Path(__file__).resolve().parents[2] / "src" / "shosai"
PORT: Final = Path("core") / "ai"
PROVIDER_HOSTS: Final = (
    "openrouter.ai",
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "api.mistral.ai",
)


def hosts_outside_the_port(root: Path) -> list[str]:
    """`file: host` for every provider host named outside `core/ai` under the root."""
    found = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if relative.is_relative_to(PORT):
            continue
        text = path.read_text(encoding="utf-8")
        found += [f"{relative}: {host}" for host in PROVIDER_HOSTS if host in text]
    return found


def test_no_provider_host_is_named_outside_the_port() -> None:
    assert hosts_outside_the_port(SOURCE) == []


def test_a_planted_host_outside_the_port_is_found(tmp_path: Path) -> None:
    (tmp_path / "core" / "ai").mkdir(parents=True)
    (tmp_path / "core" / "ai" / "adapter.py").write_text('URL = "https://openrouter.ai/api/v1"')
    (tmp_path / "features" / "notes").mkdir(parents=True)
    planted = tmp_path / "features" / "notes" / "summary.py"
    planted.write_text('URL = "https://api.openai.com/v1/chat/completions"')

    assert hosts_outside_the_port(tmp_path) == [
        f"{Path('features') / 'notes' / 'summary.py'}: api.openai.com"
    ]
