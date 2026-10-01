#!/usr/bin/env python3
"""PreToolUse-хук: не даёт писать код и выполнять команды зоны, пока не загружены её скиллы.

Зоны и скиллы — из раздела "Mandatory skills" в `.claude/CLAUDE.md`:

- правка файла (Edit, Write, MultiEdit, NotebookEdit) в `backend/`, `frontend/` или
  Docker-файла чистовика;
- команда Bash, которая что-то меняет или запускает в этих зонах (в том числе через
  `cd backend && …`), любая изменяющая команда `docker`, а также гейты качества:
  `python-doctor` и `mypy` требуют скилл `python-doctor`, `react-doctor` — `react-doctor`.

Команды только для чтения (`ls`, `cat`, `grep`, `git diff`, `docker ps` и т. п.) не
блокируются. Какие скиллы уже загружены, хук узнаёт из транскрипта сессии: вызовы
инструмента `Skill` и слэш-команды вида `/fastapi`.

Код выхода 2 блокирует действие, а текст из stderr получает агент. При собственной
ошибке (нет транскрипта, битый JSON) хук пропускает действие: сломанная проверка не
должна останавливать работу.
"""

import json
import os
import re
import shlex
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePosixPath

ZONE_SKILLS = {
    "backend": ("fastapi",),
    "frontend": (
        "vercel-react-best-practices",
        "vercel-composition-patterns",
        "vercel-react-view-transitions",
        "web-design-guidelines",
    ),
    "docker": (
        "docker-project-foundations",
        "docker-build-strategies",
        "docker-compose-patterns",
        "docker-destructive-guardrails",
    ),
}
GATE_SKILLS = {"python-doctor": "python-doctor", "mypy": "python-doctor", "react-doctor": "react-doctor"}
GATE_ZONES = {"python-doctor": "backend", "react-doctor": "frontend"}

EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
READ_ONLY_COMMANDS = frozenset(
    "ls cat head tail less more grep egrep fgrep rg find wc tree stat file du df pwd "
    "echo printf diff cmp jq sort uniq cut tr basename dirname realpath readlink which "
    "type true test sed awk".split()
)
READ_ONLY_GIT = frozenset("status diff log show blame ls-files ls-tree rev-parse grep shortlog describe".split())
READ_ONLY_DOCKER = frozenset("ps images logs inspect version info stats top events history df ls port".split())
DOCKER_OBJECTS = frozenset("compose image container volume network system buildx builder context".split())
SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n]")
WRITE_REDIRECT = re.compile(r"(?<![0-9&])>(?!&)|[0-9]>(?!&)")
SAFE_REDIRECT = re.compile(r"[0-9]?>+\s*/dev/null|[0-9]>&[0-9]")
ZONE_TOKEN = re.compile(r"(?<![\w/.-])(?:\./)?(backend|frontend)(?:/|$)")
DOCKER_FILE = re.compile(
    r"(?<![\w.-])(Dockerfile[\w.-]*|[\w.-]+\.dockerfile|\.dockerignore|"
    r"(?:docker-)?compose[\w.-]*\.ya?ml)(?![\w.-])",
    re.IGNORECASE,
)
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(?P<tag>\w+)\1")
INTERPRETERS = frozenset({"python", "python3", "node", "bash", "sh", "zsh", "ruby", "perl", "deno", "uv"})
COMMAND_PREFIXES = frozenset({"sudo", "time", "env", "nice", "timeout", "exec", "command"})


def zones_of_path(path: Path, project: Path) -> set[str]:
    """Зоны, к которым относится путь; пустое множество — путь вне чистовика или вне зон."""
    try:
        relative = PurePosixPath(path.resolve().relative_to(project).as_posix())
    except ValueError:
        return set()
    zones: set[str] = set()
    if relative.parts and relative.parts[0] in ("backend", "frontend"):
        zones.add(relative.parts[0])
    if DOCKER_FILE.fullmatch(relative.name):
        zones.add("docker")
    return zones


def command_words(segment: str) -> list[str]:
    """Слова сегмента команды без присваиваний переменных и префиксов вроде sudo."""
    try:
        words = shlex.split(segment, comments=True)
    except ValueError:
        words = segment.split()
    while words and (ENV_ASSIGNMENT.match(words[0]) or words[0] in COMMAND_PREFIXES):
        words = words[1:]
    return words


def is_read_only(words: list[str], segment: str) -> bool:
    """Сегмент ничего не меняет: команда из списка чтения и без записи в файл."""
    if not words or WRITE_REDIRECT.search(SAFE_REDIRECT.sub("", segment)):
        return False
    name = Path(words[0]).name
    if name == "sed":
        return not any(word.startswith("-i") or word == "--in-place" for word in words[1:])
    if name == "find":
        return not {"-delete", "-exec", "-execdir", "-ok"}.intersection(words)
    if name == "git":
        subcommand = next((word for word in words[1:] if not word.startswith("-")), "")
        return subcommand in READ_ONLY_GIT
    if name in ("docker", "docker-compose"):
        return docker_read_only(words)
    return name in READ_ONLY_COMMANDS


def docker_read_only(words: list[str]) -> bool:
    """Команда docker только читает: ps, logs, inspect, `compose ps`, `image ls` и т. п."""
    arguments = [word for word in words[1:] if not word.startswith("-")]
    if Path(words[0]).name == "docker-compose":
        arguments = ["compose", *arguments]
    if arguments and arguments[0] in DOCKER_OBJECTS:
        arguments = arguments[1:]
    return bool(arguments) and arguments[0] in READ_ONLY_DOCKER


def path_tokens(words: list[str], segment: str, project: Path) -> Iterator[str]:
    """Всё, что в сегменте похоже на путь: слова, цели перенаправлений, пути внутри строк."""
    for word in words:
        candidate = word.lstrip("<>&0123456789").strip("'\"")
        if "/" in candidate or DOCKER_FILE.fullmatch(candidate):
            yield candidate
    yield from (match.group(1) for match in ZONE_TOKEN.finditer(segment))
    absolute = re.compile(re.escape(str(project)) + r"/[^\s'\"`;|&)]+")
    yield from (match.group(0) for match in absolute.finditer(segment))


def segment_requirements(words: list[str], segment: str, cwd: Path, project: Path) -> set[str]:
    """Скиллы, которых требует один изменяющий сегмент команды."""
    zones = zones_of_path(cwd, project)
    for token in path_tokens(words, segment, project):
        zones |= zones_of_path(cwd / os.path.expanduser(token), project)
    if words and Path(words[0]).name in ("docker", "docker-compose"):
        zones.add("docker")
    skills = {skill for zone in zones for skill in ZONE_SKILLS[zone]}
    gates = {GATE_SKILLS[name] for word in words if (name := Path(word).name) in GATE_SKILLS}
    if words[:1] == ["npm"] and "doctor" in words[1:4]:
        gates.add("react-doctor")
    # Гейты качества — это гейты своей зоны: mypy по скрипту вне backend/ гейтом не является.
    skills |= {gate for gate in gates if GATE_ZONES[gate] in zones}
    return skills


def split_heredocs(command: str) -> tuple[str, list[str]]:
    """Отделяет тела heredoc от команды.

    Тело, которое читает интерпретатор (`python3 - <<EOF`), — это код, и его пути
    проверяются. Тело для `cat > файл <<EOF` или `git commit -F -` — это данные: важна
    только цель записи, которая остаётся в самой команде.
    """
    kept: list[str] = []
    executed: list[str] = []
    lines = iter(command.split("\n"))
    for line in lines:
        kept.append(line)
        for marker in HEREDOC.finditer(line):
            head = command_words(SEGMENT_SPLIT.split(line[: marker.start()])[-1])
            body: list[str] = []
            for body_line in lines:
                if body_line.strip() == marker.group("tag"):
                    break
                body.append(body_line)
            if head and Path(head[0]).name.rstrip("0123456789.") in INTERPRETERS:
                executed.append("\n".join(body))
    return "\n".join(kept), executed


def bash_requirements(command: str, cwd: Path, project: Path) -> set[str]:
    """Скиллы для команды Bash: объединение по всем изменяющим сегментам."""
    command, executed_bodies = split_heredocs(command)
    skills: set[str] = set()
    for body in executed_bodies:
        skills |= segment_requirements([], body, cwd, project)
    for segment in SEGMENT_SPLIT.split(command):
        words = command_words(segment)
        if words and words[0] == "cd":
            target = Path(os.path.expanduser(words[1])) if len(words) > 1 else Path.home()
            cwd = (cwd / target).resolve()
            continue
        if not is_read_only(words, segment):
            skills |= segment_requirements(words, segment, cwd, project)
    return skills


def loaded_skills(paths: Iterable[str]) -> set[str]:
    """Скиллы, загруженные в сессии, по её транскриптам (JSONL)."""
    loaded: set[str] = set()
    for raw_path in paths:
        with open(raw_path, encoding="utf-8", errors="replace") as transcript:
            for line in transcript:
                if '"Skill"' in line or "<command-name>/" in line:
                    loaded.update(skills_in_line(line))
    return loaded


def skills_in_line(line: str) -> Iterator[str]:
    """Имена скиллов из одной записи транскрипта."""
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return
    message = entry.get("message") if isinstance(entry, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    yield from skills_in_content(content)


def skills_in_content(content: object) -> Iterator[str]:
    """Вызовы инструмента Skill и слэш-команды внутри содержимого сообщения."""
    if isinstance(content, str):
        for chunk in content.split("<command-name>/")[1:]:
            yield chunk.split("<", 1)[0].strip()
        return
    if not isinstance(content, list):
        return
    for item in content:
        if not isinstance(item, dict):
            continue
        tool_input = item.get("input")
        if item.get("name") == "Skill" and isinstance(tool_input, dict):
            skill = tool_input.get("skill")
            if isinstance(skill, str):
                yield skill
        elif item.get("type") == "text":
            yield from skills_in_content(item.get("text"))


def requirements(payload: dict[str, object], project: Path) -> tuple[set[str], str]:
    """Нужные скиллы и описание действия для сообщения агенту."""
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return set(), ""
    cwd = Path(str(payload.get("cwd") or project))
    if tool_name in EDIT_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not isinstance(target, str):
            return set(), ""
        zones = zones_of_path(cwd / target, project)
        return {skill for zone in zones for skill in ZONE_SKILLS[zone]}, f"editing {target}"
    if tool_name == "Bash" and isinstance(tool_input.get("command"), str):
        command = str(tool_input["command"])
        return bash_requirements(command, cwd, project), f"running `{command[:80]}`"
    return set(), ""


def main() -> int:
    """Возвращает 2 и объясняет агенту, какие скиллы загрузить, если их нет."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or str(payload.get("cwd") or ".")).resolve()
    needed, action = requirements(payload, project)
    transcripts = [
        str(value)
        for key in ("transcript_path", "agent_transcript_path")
        if (value := payload.get(key)) and Path(str(value)).is_file()
    ]
    if not needed or not transcripts:
        return 0
    missing = sorted(needed - loaded_skills(transcripts))
    if not missing:
        return 0
    print(
        f"Blocked {action}: the mandatory skills for this zone are not loaded in this "
        f"session: {', '.join(missing)}. Load each one with the Skill tool and follow it "
        "(CLAUDE.md, 'Mandatory skills'), then retry.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
