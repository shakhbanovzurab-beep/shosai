"""Where a skill comes from, and what its SKILL.md says (ADR 0068 AG-D11; agent step 15).

A person installs a skill by what they copied: `owner/repo/path/to/folder`, a GitHub link to
the folder or its SKILL.md (`/tree/<ref>/…`, `/blob/<ref>/…`, whose ref is kept and pinned —
the draft always took the default branch), or a skills.sh id or link, `owner/repo/name`, whose
last segment names the skill rather than its folder: it is found in the repository's tree. A
repository is `owner/repo`, bare or as a link. Every segment comes from an allow-list, since
it goes into GitHub's URLs, and a path is at most five folders deep and 255 characters long.

SKILL.md is the Agent Skills format: YAML front matter between `---` lines, with `name` and
`description`, then the instructions. Only `key: value` lines and folded or literal block
scalars are read — two fields do not need a YAML parser. The body is kept up to 24 000
characters, cut with a note, since a prompt carries it on every call.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from urllib.parse import urlsplit

REPO_SEGMENT: Final = re.compile(r"[A-Za-z0-9._-]{1,100}")
OWNER: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}")
PATH_SEGMENT: Final = re.compile(r"[A-Za-z0-9._:-]{1,64}")
REF: Final = re.compile(r"[A-Za-z0-9._/-]{1,80}")
MAX_DEPTH: Final = 5
MAX_PATH: Final = 255
SKILL_FILE: Final = "SKILL.md"
BODY_CHARS: Final = 24_000
NAME_CHARS: Final = 80
DESCRIPTION_CHARS: Final = 600
# Метка обрезки читается моделью в промпте: только английский (CLAUDE.md, Prompts).
CUT_NOTE: Final = "\n\n[The skill was cut at the platform's limit.]"
GITHUB_HOSTS: Final = frozenset({"github.com", "www.github.com"})
SKILLS_HOSTS: Final = frozenset({"skills.sh", "www.skills.sh"})
FRONT_MATTER: Final = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.DOTALL)
FIELD: Final = re.compile(r"([\w-]+):\s*(.*)")
BLOCK_SCALAR: Final = re.compile(r"[>|][-+]?")


class SkillSourceError(ValueError):
    """A reference or a SKILL.md that cannot be used; the value is the API's error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SourceKind(StrEnum):
    """How the person named the skill: its folder on GitHub, or its skills.sh id."""

    GITHUB = "github"
    SKILLS_SH = "skills_sh"


@dataclass(frozen=True, slots=True)
class SkillReference:
    """A skill to install: its repository, the folder or the name, and the ref to pin."""

    repository: str
    path: str
    kind: SourceKind
    ref: str | None = None

    @property
    def name_hint(self) -> str:
        """The last segment: the folder's name, or the skills.sh id's skill."""
        return self.path.rsplit("/", 1)[-1]


@dataclass(frozen=True, slots=True)
class Manifest:
    """What SKILL.md says: its name and description, and the instructions."""

    name: str
    description: str
    body: str


def repository_of(raw: str) -> str:
    """`owner/repo` from what the person typed or pasted."""
    host, parts = split_source(raw)
    if host not in GITHUB_HOSTS | {""} or len(parts) < 2:
        raise SkillSourceError("repository_invalid")
    return checked_repository(parts[0], parts[1])


def reference_of(raw: str) -> SkillReference:
    """The skill a reference names; a skills.sh one by its name, a GitHub one by its folder."""
    host, parts = split_source(raw)
    if host not in GITHUB_HOSTS | SKILLS_HOSTS | {""} or len(parts) < 2:
        raise SkillSourceError("skill_reference_invalid")
    repository = checked_repository(parts[0], parts[1])
    rest, ref = parts[2:], None
    if host in GITHUB_HOSTS and len(rest) >= 2 and rest[0] in {"tree", "blob"}:
        ref, rest = rest[1], rest[2:]
        if not REF.fullmatch(ref):
            raise SkillSourceError("skill_reference_invalid")
    if rest and rest[-1] == SKILL_FILE:
        rest = rest[:-1]
    path = checked_path(rest)
    kind = SourceKind.SKILLS_SH if host in SKILLS_HOSTS else SourceKind.GITHUB
    return SkillReference(repository, path, kind, ref)


def split_source(raw: str) -> tuple[str, list[str]]:
    """The host, if a link, and the path's segments; query and fragment dropped."""
    text = raw.strip()
    if "://" not in text and text.split("/", 1)[0].lower() in GITHUB_HOSTS | SKILLS_HOSTS:
        text = f"https://{text}"
    if "://" in text:
        parsed = urlsplit(text)
        host, path = (parsed.hostname or "").lower(), parsed.path
    else:
        host, path = "", text.split("?", 1)[0].split("#", 1)[0]
    return host, [part for part in path.split("/") if part]


def checked_repository(owner: str, repo: str) -> str:
    """`owner/repo` when both are GitHub-shaped."""
    repo = repo.removesuffix(".git")
    if not OWNER.fullmatch(owner) or not REPO_SEGMENT.fullmatch(repo) or repo in {".", ".."}:
        raise SkillSourceError("repository_invalid")
    return f"{owner}/{repo}"


def checked_path(segments: list[str]) -> str:
    """A folder inside the repository: allow-listed segments, never `.` or `..`."""
    if len(segments) > MAX_DEPTH:
        raise SkillSourceError("skill_reference_invalid")
    for segment in segments:
        if segment in {".", ".."} or not PATH_SEGMENT.fullmatch(segment):
            raise SkillSourceError("skill_reference_invalid")
    path = "/".join(segments)
    if len(path) > MAX_PATH:
        raise SkillSourceError("skill_reference_invalid")
    return path


def manifest_of(text: str) -> Manifest:
    """SKILL.md's fields and body; without front matter or instructions it is no skill."""
    match = FRONT_MATTER.match(text.lstrip("﻿"))
    if match is None:
        raise SkillSourceError("no_frontmatter")
    fields = front_matter(match.group(1))
    body = match.group(2).strip()
    if not body:
        raise SkillSourceError("skill_file_empty")
    if len(body) > BODY_CHARS:
        body = body[: BODY_CHARS - len(CUT_NOTE)].rstrip() + CUT_NOTE
    return Manifest(
        name=fields.get("name", "").strip()[:NAME_CHARS],
        description=fields.get("description", "").strip()[:DESCRIPTION_CHARS],
        body=body,
    )


def front_matter(block: str) -> dict[str, str]:
    """`key: value` lines, quotes taken off; a block scalar's indented lines joined."""
    fields: dict[str, str] = {}
    current: str | None = None
    for line in block.splitlines():
        field = FIELD.fullmatch(line)
        if field is not None:
            current, value = field.group(1), field.group(2).strip()
            fields[current] = "" if BLOCK_SCALAR.fullmatch(value) else value.strip("'\"")
        elif current is not None and line[:1] in {" ", "\t"} and line.strip():
            fields[current] = f"{fields[current]} {line.strip()}".strip()
    return fields
