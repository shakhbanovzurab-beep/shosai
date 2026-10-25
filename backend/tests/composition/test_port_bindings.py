"""Every single-implementation port a slice reads is bound by some slice (ADR 0045 point 11).

A slice reads a port by its key, `ports.get(KEY)`, and the slice that implements it binds the
key in its module, `KEY.bind(...)`. A read that nobody binds fails only when that code runs —
a turn asked from a board page did, until `tasks.board_reader` was bound — so the sources are
checked here. The evaluation harness binds its own doubles and does not count.
"""

import ast
from pathlib import Path
from typing import Final

SOURCES: Final = Path(__file__).resolve().parents[2] / "src" / "shosai"
# Мир оценки Leo привязывает свои дублёры портов: это не привязка платформы.
DOUBLES: Final = frozenset({"eval_world.py"})


def _key(node: ast.expr) -> str | None:
    return node.id if isinstance(node, ast.Name) and node.id.isupper() else None


def _uses() -> tuple[dict[str, set[str]], set[str]]:
    read: dict[str, set[str]] = {}
    bound: set[str] = set()
    for path in SOURCES.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            call = node.func
            if call.attr == "get" and node.args and "ports" in ast.unparse(call.value):
                key = _key(node.args[0])
                if key is not None:
                    read.setdefault(key, set()).add(str(path.relative_to(SOURCES)))
            bound_key = _key(call.value) if call.attr == "bind" else None
            if bound_key is not None and path.name not in DOUBLES:
                bound.add(bound_key)
    return read, bound


def test_every_port_a_slice_reads_by_get_is_bound_by_some_slice() -> None:
    read, bound = _uses()

    unbound = {key: sorted(paths) for key, paths in read.items() if key not in bound}

    assert read, "сканер не нашёл ни одного чтения порта: поменялся вид вызова"
    assert unbound == {}
