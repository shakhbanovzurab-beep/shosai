"""The world an evaluated turn runs in: a made-up person and what the scenario shows (AG-D8).

Every scenario runs for a new person who exists only for that run: the other slices' ports the
turn reads are answered here, by the scenario — a plan with every capability and tokens to
spare, a profile in the run's language, no workspaces, and the page's meeting, task, board or
file as the scenario describes it. The person's rows are erased after the run through the
slices' own erasure handlers, so the eval leaves nothing behind.
"""

from collections.abc import Collection, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shosai.core.kernel.homes import Home
from shosai.core.ports.keys import PortBinding
from shosai.core.storage.port import ObjectStream
from shosai.features.agent.application.eval_stage import EvalStage
from shosai.features.agent.domain.eval_cases import EvalSubject
from shosai.features.billing.contracts import (
    ENTITLEMENTS,
    TOKEN_ALLOWANCE,
    Audience,
    Capability,
    EntitlementSnapshot,
    EntitlementSource,
    ModelTier,
    PlanLimits,
    TokenDecision,
    TokenRoute,
)
from shosai.features.files.contracts import FILE_READER, FileFacts, FileKind
from shosai.features.identity.contracts import (
    ACCOUNT_PROFILE_READER,
    CONSENT_READER,
    AccountProfile,
)
from shosai.features.notes.contracts import (
    MEETING_READER,
    MeetingFacts,
    MeetingStatus,
    TranscriptPage,
)
from shosai.features.tasks.contracts import (
    BOARD_READER,
    TASK_READER,
    Assignee,
    BoardFacts,
    TaskFacts,
    TaskSource,
    TaskStatus,
)
from shosai.features.workspaces.contracts import (
    MEMBERSHIP_READER,
    WORKSPACE_READER,
    ActiveMembership,
    Viewer,
    WorkspaceFacts,
)

PERSON_NAME: Final = "Anna Petrova"
TIME_ZONE: Final = "Europe/Berlin"
MEETING_STARTED: Final = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
MEETING_LENGTH: Final = timedelta(minutes=45)
FILE_SIZE: Final = 120_000
# Автор чужого предмета страницы: коллега, которого нет нигде, кроме прогона.
COLLEAGUE: Final = UUID("00000000-0000-7000-8000-00000000c011")


class EvalTerms:
    """A plan with every capability, tokens within the allowance, consent given."""

    async def decision(self, home: Home, user_id: UUID, tier: ModelTier) -> TokenDecision:
        """Within the allowance."""
        del home, user_id, tier
        return TokenDecision(TokenRoute.WITHIN_ALLOWANCE)

    async def snapshot(self, home: Home, user_id: UUID) -> EntitlementSnapshot:
        """Every capability, no limit."""
        del home
        return EntitlementSnapshot(
            user_id=user_id, plan_slug="eval", plan_name="Evaluation",
            audience=Audience.INDIVIDUAL, paid=True, in_grace=False, paid_until=None,
            limits=PlanLimits(None, None, None), capabilities=frozenset(Capability),
            source=EntitlementSource.PERSONAL, workspace_id=None, version=1,
        )  # fmt: skip

    async def cross_border(self, session: AsyncSession, user_id: UUID) -> bool:
        """Consent given."""
        del session, user_id
        return True

    async def improve_models(self, session: AsyncSession, user_id: UUID) -> bool:
        """The world's person never shares a turn: an eval makes no case."""
        del session, user_id
        return False


@dataclass(frozen=True, slots=True)
class EvalPeople:
    """The person's profile in the run's language."""

    stage: EvalStage

    async def profile(self, session: AsyncSession, user_id: UUID) -> AccountProfile | None:
        """A fixed name and zone; the run's language."""
        del session
        staged = self.stage.of(user_id)
        return AccountProfile(PERSON_NAME, staged.language if staged else "en", TIME_ZONE)

    async def names(self, session: AsyncSession, user_ids: Collection[UUID]) -> Mapping[UUID, str]:
        """Everyone has the same name here."""
        del session
        return dict.fromkeys(user_ids, PERSON_NAME)


def owner_of(subject: EvalSubject, viewer: Viewer) -> UUID:
    """The subject's author: the person, or a colleague."""
    return viewer.user_id if subject.own else COLLEAGUE


@dataclass(frozen=True, slots=True)
class EvalMeetings:
    """The page's meeting, as the scenario describes it."""

    stage: EvalStage

    async def facts(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[UUID]
    ) -> Mapping[UUID, MeetingFacts]:
        """The staged meeting among the ids."""
        del session
        subject = self.stage.subject(viewer.user_id, "meeting", meeting_ids)
        if subject is None:
            return {}
        return {
            subject.id: MeetingFacts(
                meeting_id=subject.id, user_id=owner_of(subject, viewer), org_id=None,
                title=subject.title, status=MeetingStatus.COMPLETED, started_at=MEETING_STARTED,
                ended_at=MEETING_STARTED + MEETING_LENGTH,
                seconds=int(MEETING_LENGTH.total_seconds()), participants=(),
                summary=subject.summary,
            )
        }  # fmt: skip

    async def readable(
        self, session: AsyncSession, viewer: Viewer, meeting_ids: Collection[UUID]
    ) -> frozenset[UUID]:
        """The staged meeting among the ids."""
        return frozenset(await self.facts(session, viewer, meeting_ids))

    async def transcript(
        self, home: Home, viewer: Viewer, meeting_id: UUID, cursor: str | None, limit: int
    ) -> TranscriptPage:
        """The turn reads speech through the tools, never this way."""
        del home, viewer, meeting_id, cursor, limit
        return TranscriptPage((), None)


@dataclass(frozen=True, slots=True)
class EvalTasks:
    """The page's task and board."""

    stage: EvalStage

    async def facts(
        self, session: AsyncSession, viewer: Viewer, task_ids: Collection[UUID]
    ) -> Mapping[UUID, TaskFacts]:
        """The staged task among the ids."""
        del session
        subject = self.stage.subject(viewer.user_id, "task", task_ids)
        if subject is None:
            return {}
        return {
            subject.id: TaskFacts(
                task_id=subject.id, user_id=owner_of(subject, viewer), org_id=None,
                title=subject.title, status=TaskStatus.TODO, priority=None, due_on=None,
                assignee=Assignee(), source=TaskSource.MANUAL, source_meeting_id=None,
            )
        }  # fmt: skip

    async def boards(self, session: AsyncSession, user_id: UUID) -> Sequence[BoardFacts]:
        """The staged board, the person's only one."""
        del session
        staged = self.stage.of(user_id)
        subject = staged.scenario.subject if staged is not None else None
        if subject is None or subject.kind != "board":
            return ()
        return (BoardFacts(subject.id, subject.title, synced_with_jira=False),)

    async def exists(self, session: AsyncSession, user_id: UUID, board_id: UUID) -> bool:
        """Whether the board is the staged one."""
        return any(board.board_id == board_id for board in await self.boards(session, user_id))


@dataclass(frozen=True, slots=True)
class EvalFiles:
    """The page's file."""

    stage: EvalStage

    async def facts(
        self, session: AsyncSession, viewer: Viewer, file_ids: Sequence[UUID]
    ) -> Mapping[UUID, FileFacts]:
        """The staged file among the ids."""
        del session
        subject = self.stage.subject(viewer.user_id, "file", file_ids)
        if subject is None:
            return {}
        return {
            subject.id: FileFacts(
                subject.id,
                subject.title,
                FileKind.DOCUMENT,
                "application/pdf",
                FILE_SIZE,
                leo_readable=True,
                owner_id=owner_of(subject, viewer),
            )
        }

    def open(
        self, home: Home, viewer: Viewer, file_id: UUID
    ) -> AbstractAsyncContextManager[ObjectStream]:
        """A file's bytes are never read by a turn's context."""
        del home, viewer
        message = f"файл {file_id} в оценке не открывается"
        raise LookupError(message)


class EvalSpaces:
    """No workspaces: the person works in Personal only."""

    async def active(self, session: AsyncSession, user_id: UUID) -> tuple[ActiveMembership, ...]:
        """None."""
        del session, user_id
        return ()

    async def has_memberships(self, session: AsyncSession, user_id: UUID) -> bool:
        """None."""
        del session, user_id
        return False

    async def members(
        self, session: AsyncSession, org_id: UUID, user_ids: Collection[UUID]
    ) -> Mapping[UUID, ActiveMembership]:
        """None."""
        del session, org_id, user_ids
        return {}

    async def projects(
        self, session: AsyncSession, org_id: UUID, project_ids: Collection[UUID]
    ) -> frozenset[UUID]:
        """None."""
        del session, org_id, project_ids
        return frozenset()

    async def workspaces(
        self, session: AsyncSession, org_ids: Collection[UUID]
    ) -> Mapping[UUID, WorkspaceFacts]:
        """None."""
        del session, org_ids
        return {}


def world_bindings(stage: EvalStage) -> tuple[PortBinding[Any], ...]:
    """Every port an evaluated turn reads, bound to the scenario's world."""
    terms, tasks, spaces = EvalTerms(), EvalTasks(stage), EvalSpaces()
    return (
        TOKEN_ALLOWANCE.bind(terms),
        ENTITLEMENTS.bind(terms),
        CONSENT_READER.bind(terms),
        ACCOUNT_PROFILE_READER.bind(EvalPeople(stage)),
        MEETING_READER.bind(EvalMeetings(stage)),
        TASK_READER.bind(tasks),
        BOARD_READER.bind(tasks),
        FILE_READER.bind(EvalFiles(stage)),
        MEMBERSHIP_READER.bind(spaces),
        WORKSPACE_READER.bind(spaces),
    )
