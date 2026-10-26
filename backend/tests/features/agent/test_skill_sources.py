"""What a skill reference names and what SKILL.md says (agent step 15): the ref of a link kept,
a skills.sh id looked up by name, unsafe paths refused, the front matter read without YAML, the
body cut at its cap; a repository's skills found in its tree."""

import pytest

from shosai.features.agent.domain.skill_sources import (
    BODY_CHARS,
    CUT_NOTE,
    SkillReference,
    SkillSourceError,
    SourceKind,
    manifest_of,
    reference_of,
    repository_of,
)
from shosai.features.agent.domain.skill_tree import (
    TreeEntry,
    every_skill_folder,
    has_extra_files,
    previewed_folders,
    resolved_folder,
)

GITHUB = SourceKind.GITHUB


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("acme/kit/skills/pdf", SkillReference("acme/kit", "skills/pdf", GITHUB)),
        ("acme/kit", SkillReference("acme/kit", "", GITHUB)),
        (
            "https://github.com/acme/kit/tree/v1.2/skills/pdf",
            SkillReference("acme/kit", "skills/pdf", GITHUB, "v1.2"),
        ),
        (
            "github.com/acme/kit/blob/main/skills/pdf/SKILL.md?plain=1",
            SkillReference("acme/kit", "skills/pdf", GITHUB, "main"),
        ),
        ("https://skills.sh/acme/kit/pdf", SkillReference("acme/kit", "pdf", SourceKind.SKILLS_SH)),
        ("acme/kit/ns::pdf-tools", SkillReference("acme/kit", "ns::pdf-tools", GITHUB)),
    ],
)
def test_a_reference_names_its_repository_folder_and_ref(
    raw: str, expected: SkillReference
) -> None:
    assert reference_of(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "acme", "acme/kit/../secrets", "https://gitlab.com/acme/kit/x", "acme/kit/a/b/c/d/e/f",
        "acme/kit/has space", "-/kit/x", "acme/kit/tree/../x",
    ],
)  # fmt: skip
def test_a_reference_outside_the_allow_list_is_refused(raw: str) -> None:
    with pytest.raises(SkillSourceError):
        reference_of(raw)


def test_a_repository_is_owner_and_name_from_any_of_its_links() -> None:
    assert repository_of("https://github.com/acme/kit.git") == "acme/kit"
    assert repository_of(" acme/kit/tree/main/skills ") == "acme/kit"
    with pytest.raises(SkillSourceError, match="repository_invalid"):
        repository_of("https://skills.sh/acme/kit")


def test_skill_md_gives_its_fields_and_body_without_a_yaml_parser() -> None:
    text = (
        "﻿---\nname: 'pdf'\ndescription: >\n  Reads PDFs,\n  fills forms.\nlicense: MIT\n"
        "---\n\n# PDF\nDo the work.\n"
    )

    manifest = manifest_of(text)

    assert (manifest.name, manifest.description) == ("pdf", "Reads PDFs, fills forms.")
    assert manifest.body == "# PDF\nDo the work."


def test_a_long_body_is_cut_with_a_note_and_a_file_without_front_matter_is_no_skill() -> None:
    long = manifest_of("---\nname: x\n---\n" + "y" * (BODY_CHARS + 50))

    assert len(long.body) <= BODY_CHARS
    assert long.body.endswith(CUT_NOTE)
    with pytest.raises(SkillSourceError, match="no_frontmatter"):
        manifest_of("# Just markdown")
    with pytest.raises(SkillSourceError, match="skill_file_empty"):
        manifest_of("---\nname: x\n---\n   \n")


TREE = [
    TreeEntry("README.md", "blob"),
    TreeEntry("SKILL.md", "blob"),
    TreeEntry("skills/pdf/SKILL.md", "blob"),
    TreeEntry("skills/pdf/scripts/fill.py", "blob"),
    TreeEntry("skills/docx/SKILL.md", "blob"),
    TreeEntry("vendor/pdf/SKILL.md", "blob"),
    TreeEntry("examples/demo/SKILL.md", "blob"),
    TreeEntry(".github/skill/SKILL.md", "blob"),
    TreeEntry("tools/a/xlsx/SKILL.md", "blob"),
    TreeEntry("tools/b/xlsx/SKILL.md", "blob"),
    TreeEntry("skills", "tree"),
]


def test_a_scan_lists_skills_shallow_first_without_examples_or_hidden_folders() -> None:
    assert previewed_folders(TREE) == [
        "", "skills/docx", "skills/pdf", "vendor/pdf", "tools/a/xlsx", "tools/b/xlsx",
    ]  # fmt: skip
    assert "examples/demo" in every_skill_folder(TREE)


@pytest.mark.parametrize(
    ("reference", "folder"),
    [
        (SkillReference("acme/kit", "examples/demo", GITHUB), "examples/demo"),
        (SkillReference("acme/kit", "pdf", SourceKind.SKILLS_SH), "skills/pdf"),
        (SkillReference("acme/kit", "docx", GITHUB), "skills/docx"),
        (SkillReference("acme/kit", "", GITHUB), ""),
    ],
)
def test_a_reference_finds_its_folder_by_path_then_by_name(
    reference: SkillReference, folder: str
) -> None:
    assert resolved_folder(reference, every_skill_folder(TREE)) == folder


@pytest.mark.parametrize(
    ("path", "code"),
    [("xlsx", "ambiguous_skill"), ("pptx", "skill_not_found"), ("a/pdf", "skill_not_found")],
)
def test_a_name_with_two_folders_is_ambiguous_and_none_is_not_found(path: str, code: str) -> None:
    with pytest.raises(SkillSourceError, match=code):
        resolved_folder(SkillReference("acme/kit", path, GITHUB), every_skill_folder(TREE))


def test_extra_files_are_those_beside_skill_md_in_its_folder() -> None:
    assert has_extra_files(TREE, "skills/pdf")
    assert not has_extra_files(TREE, "skills/docx")
