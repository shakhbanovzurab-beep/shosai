"""The native import's rules: the names, the job's stages and a failure's words (step 9b)."""

from itertools import pairwise

from hypothesis import given
from hypothesis import strategies as st

from shosai.core.i18n.locales import LOCALES
from shosai.features.notes.channels.http.native_import_texts import (
    FAILURE_TEXTS,
    OTHER_FAILURE,
    failure_text,
)
from shosai.features.notes.domain.native_import import (
    FILENAME_MAX,
    JobStage,
    accepted_name,
    job_progress,
    media_type_of,
    stored_name,
)
from shosai.features.notes.domain.runs import (
    NON_CRITICAL,
    STAGES,
    RunSource,
    RunState,
    Stage,
    StageRecord,
    StageStatus,
    outcome,
)

RANK = {
    JobStage.UPLOADING: 0, JobStage.TRANSCRIBING: 1, JobStage.ENHANCING: 2,
    JobStage.READY: 3, JobStage.FAILED: 3,
}  # fmt: skip
IMPORT_STAGES = STAGES[RunSource.IMPORT]
CODES = (
    "upload_exceeds_minutes", "recording_too_long", "unsupported_audio_format",
    "media_unreadable", "consent_required", "transcript_empty",
)  # fmt: skip


def test_the_draft_s_names_are_taken_and_kept_by_their_last_segment() -> None:
    assert accepted_name("Meeting.M4A")
    assert accepted_name("call.mpga")
    assert not accepted_name("notes.txt")
    assert not accepted_name("recording")
    assert not accepted_name(None)
    assert media_type_of("Call.MP4") == "audio/mp4"
    assert stored_name("C:\\Users\\anna\\call.m4a") == "call.m4a"
    assert stored_name("dir/sub/call.ogg") == "call.ogg"
    assert len(stored_name("a" * 600 + ".mp3")) == FILENAME_MAX


def test_a_job_reads_its_run_through_the_five_stages() -> None:
    def at(**states: StageStatus) -> dict[Stage, StageRecord]:
        return {Stage(name): StageRecord(status, 1) for name, status in states.items()}

    done, running = StageStatus.DONE, StageStatus.RUNNING
    assert job_progress(RunState.PENDING, {}) == (JobStage.UPLOADING, 0.0)
    assert job_progress(RunState.RUNNING, at(intake=running)) == (JobStage.TRANSCRIBING, 0.0)
    assert job_progress(RunState.RUNNING, at(intake=done, transcribe=done)) == (
        JobStage.TRANSCRIBING, 0.33,
    )  # fmt: skip
    four = at(intake=done, transcribe=done, diarize=StageStatus.FAILED, align=done)
    assert job_progress(RunState.RUNNING, four) == (JobStage.ENHANCING, 0.67)
    assert job_progress(RunState.PARTIALLY_COMPLETED, four) == (JobStage.READY, 1.0)
    failed = at(intake=StageStatus.FAILED)
    assert job_progress(RunState.FAILED, failed) == (JobStage.FAILED, 0.17)


@given(st.lists(st.tuples(st.integers(0, 2), st.booleans()), min_size=6, max_size=6))
def test_a_job_s_stage_and_progress_never_go_back(attempts: list[tuple[int, bool]]) -> None:
    progress: dict[Stage, StageRecord] = {}
    seen = [job_progress(RunState.PENDING, progress)]
    state = RunState.RUNNING
    for stage, (retries, fails) in zip(IMPORT_STAGES, attempts, strict=True):
        for attempt in range(1, retries + 2):
            progress[stage] = StageRecord(StageStatus.RUNNING, attempt)
            seen.append(job_progress(state, progress))
            if attempt <= retries:
                progress[stage] = StageRecord(StageStatus.PENDING, attempt, "provider_error")
                seen.append(job_progress(state, progress))
        status = StageStatus.FAILED if fails else StageStatus.DONE
        progress[stage] = StageRecord(status, retries + 1, "media_unreadable" if fails else None)
        ended = outcome(RunSource.IMPORT, progress)
        state = ended or RunState.RUNNING
        seen.append(job_progress(state, progress))
        if fails and stage not in NON_CRITICAL:
            break

    for before, after in pairwise(seen):
        assert RANK[after[0]] >= RANK[before[0]]
        assert after[1] >= before[1] or after[0] is JobStage.READY
    assert seen[-1][0] in {JobStage.READY, JobStage.FAILED}


def test_a_failure_is_worded_in_each_platform_language() -> None:
    assert {locale.code for locale in LOCALES} == set(FAILURE_TEXTS)
    for texts in FAILURE_TEXTS.values():
        assert set(texts) == {OTHER_FAILURE, *CODES}
        assert all(text.strip() for text in texts.values())
    assert failure_text("recording_too_long", "pt") == FAILURE_TEXTS["pt-BR"]["recording_too_long"]
    assert failure_text("provider_error", "ru") == FAILURE_TEXTS["ru"][OTHER_FAILURE]
    assert failure_text(None, "xx") == FAILURE_TEXTS["en"][OTHER_FAILURE]
