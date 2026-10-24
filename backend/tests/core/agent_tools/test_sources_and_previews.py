"""Sources, artifacts and the wording of previews in core's tool contract (ADR 0068)."""

import dataclasses
import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shosai.core.agent_tools.previews import (
    EMPTY,
    LANGUAGES,
    PreviewField,
    PreviewWording,
    render_preview,
)
from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.results import Preview, ToolError, ToolErrorCode, ToolResult
from shosai.core.agent_tools.sources import ArtifactKind, ArtifactRef, SourceKind, SourceRef
from tests.core.agent_tools.probe_tools import ARCHIVE, SEARCH, FoundNotes


def every(text: str) -> dict[str, str]:
    """The same text in every platform language, with the language's code in it."""
    return {code: f"{text} ({code})" for code in LANGUAGES}


def move_wording() -> PreviewWording:
    return PreviewWording(
        key="agent.probe.move",
        params=("title", "folder", "done", "note"),
        title=every("Move {title}"),
        fields=(
            PreviewField("folder", every("Folder")),
            PreviewField(
                "done", every("Done"), values={"true": every("Yes"), "false": every("No")}
            ),
        ),
        body="note",
    )


def test_a_source_names_its_space_and_is_the_same_by_its_place() -> None:
    org = uuid.uuid4()
    first = SourceRef(SourceKind.MEETING, "m-1", "Budget", org_id=org, locator="12:30", quote="Q")
    again = dataclasses.replace(first, title="Budget review", quote="Other words")

    assert first.identity == again.identity
    assert first.identity != dataclasses.replace(first, locator="40:00").identity
    with pytest.raises(ValueError, match="название"):
        SourceRef(SourceKind.FILE, "f-1", " ")


def test_an_artifact_carries_exactly_its_kind_s_fields() -> None:
    fields = {"workspace_id": str(uuid.uuid4()), "chat_id": str(uuid.uuid4())}
    digest = ArtifactRef(ArtifactKind.CHAT_DIGEST, "d-1", "Digest of #sales", fields)

    assert digest.fields == fields
    with pytest.raises(ValueError, match="поля"):
        ArtifactRef(ArtifactKind.CHAT_DIGEST, "d-1", "Digest", {"workspace_id": "w"})


def test_an_error_has_no_sources_artifacts_or_label() -> None:
    source = SourceRef(SourceKind.TASK, "t-1", "Call the bank")
    found = ToolResult(FoundNotes(titles=["a"]), sources=(source,), provenance=Provenance.FILE_OWN)

    assert (found.sources, found.provenance) == ((source,), Provenance.FILE_OWN)
    with pytest.raises(ValueError, match="ошибки"):
        ToolResult[FoundNotes](error=ToolError(ToolErrorCode.FAILED), sources=(source,))
    with pytest.raises(ValueError, match="ошибки"):
        ToolResult[FoundNotes](error=ToolError(ToolErrorCode.FAILED), provenance=Provenance.MAIL)


def test_a_card_renders_in_the_language_and_skips_empty_values() -> None:
    preview = Preview("agent.probe.move", {"title": "Plan", "folder": None, "done": True})

    card = render_preview(move_wording(), preview, "ru")

    assert card.title == "Move Plan (ru)"
    assert card.fields == (("Done (ru)", "Yes (ru)"),)
    assert card.body is None


def test_an_unknown_language_reads_english_and_a_missing_title_value_shows_a_dash() -> None:
    card = render_preview(move_wording(), Preview("agent.probe.move", {"note": "Body"}), "xx")

    assert card.title == f"Move {EMPTY} (en)"
    assert card.body == "Body"


def test_wording_must_cover_every_language_and_name_only_its_params() -> None:
    partial = {"en": "Move"}
    with pytest.raises(ValueError, match="нет языков"):
        PreviewWording("agent.probe.move", ("title",), partial)
    with pytest.raises(ValueError, match="необъявленные"):
        PreviewWording("agent.probe.move", ("title",), every("Move {folder}"))
    with pytest.raises(ValueError, match="ключ"):
        PreviewWording("probe.move", ("title",), every("Move"))


def test_previews_belong_to_writes_under_their_namespace_and_detail_names_an_argument() -> None:
    wording = dataclasses.replace(move_wording(), key="agent.notes.archive")

    assert dataclasses.replace(ARCHIVE, previews=(wording,)).previews == (wording,)
    assert dataclasses.replace(SEARCH, step_detail="query").step_detail == "query"
    with pytest.raises(ValueError, match="только у записи"):
        dataclasses.replace(SEARCH, previews=(wording,))
    with pytest.raises(ValueError, match=r"начинаются с agent\.notes\."):
        dataclasses.replace(ARCHIVE, previews=(dataclasses.replace(wording, key="agent.x.a"),))
    with pytest.raises(ValueError, match="step_detail"):
        dataclasses.replace(SEARCH, step_detail="missing")


@given(st.text(max_size=200), st.sampled_from(sorted(LANGUAGES)))
def test_a_param_s_text_is_shown_as_given(title: str, language: str) -> None:
    card = render_preview(
        move_wording(), Preview("agent.probe.move", {"title": title, "folder": title}), language
    )

    assert card.fields[0][1] == title
