"""A repository's skills, from its tree (ADR 0068 AG-D11; agent step 15).

A skill is a folder holding SKILL.md. A scan lists them shallow first — real skills sit at
`skills/<name>/`, examples and drafts deeper — skipping folders of examples, templates, drafts,
tests and hidden ones, at most 40 for a preview; installing by a path is never bounded by that
cap (the draft's 25 hid skills). A reference finds its folder by the exact path first; a
one-segment name, as skills.sh ids give, is then looked up by the folder's last segment
anywhere in the tree, `skills/<name>` preferred, and two equal candidates are ambiguous.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from shosai.features.agent.domain.skill_sources import (
    SKILL_FILE,
    SkillReference,
    SkillSourceError,
    SourceKind,
)

PREVIEWED: Final = 40
SKIPPED: Final = re.compile(
    r"([._].*|docs|templates?|drafts?|examples?|node_modules|tests?|fixtures)", re.IGNORECASE
)
SKILLS_FOLDER: Final = "skills"
BLOB: Final = "blob"


@dataclass(frozen=True, slots=True)
class TreeEntry:
    """A file or a folder of the repository at the pinned commit."""

    path: str
    kind: str


def folder_of(file: str) -> str:
    """The folder of a SKILL.md; the root is the empty path."""
    return "" if file == SKILL_FILE else file.removesuffix(f"/{SKILL_FILE}")


def every_skill_folder(tree: Sequence[TreeEntry]) -> list[str]:
    """Every folder with SKILL.md, shallow first: what a reference may name."""
    found = [
        folder_of(entry.path)
        for entry in tree
        if entry.kind == BLOB
        and (entry.path == SKILL_FILE or entry.path.endswith(f"/{SKILL_FILE}"))
    ]
    return sorted(found, key=lambda folder: (folder.count("/") + bool(folder), folder))


def previewed_folders(tree: Sequence[TreeEntry]) -> list[str]:
    """The folders a scan shows: without examples, drafts and hidden ones, at most 40."""
    return [
        folder
        for folder in every_skill_folder(tree)
        if not any(SKIPPED.fullmatch(part) for part in folder.split("/") if part)
    ][:PREVIEWED]


def resolved_folder(reference: SkillReference, folders: Sequence[str]) -> str:
    """The folder of the skill the reference names."""
    if reference.path in folders:
        return reference.path
    by_name = reference.kind is SourceKind.SKILLS_SH or "/" not in reference.path
    if not by_name or not reference.path:
        raise SkillSourceError("skill_not_found")
    name = reference.name_hint
    named = [folder for folder in folders if folder.rsplit("/", 1)[-1] == name]
    preferred = [folder for folder in named if folder == f"{SKILLS_FOLDER}/{name}"]
    if len(preferred) == 1 or len(named) == 1:
        return (preferred or named)[0]
    raise SkillSourceError("ambiguous_skill" if named else "skill_not_found")


def has_extra_files(tree: Sequence[TreeEntry], folder: str) -> bool:
    """Whether the skill's folder holds files besides SKILL.md, which Leo never runs."""
    prefix = f"{folder}/" if folder else ""
    own = f"{prefix}{SKILL_FILE}"
    return any(e.kind == BLOB and e.path.startswith(prefix) and e.path != own for e in tree)
