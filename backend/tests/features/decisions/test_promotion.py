"""Putting versions in force: passing revisions only, active only after the shadow window
(decisions plan §3.5, DL-D6)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from shosai.features.decisions.application.promotion import Promotion
from shosai.features.decisions.domain.policies import policies_by_key
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from shosai.features.decisions.infrastructure.policy_admin import StoredRevision, VersionState

NOW = datetime(2026, 11, 20, tzinfo=UTC)
KEY = "action.friction@1"


@dataclass
class Admin:
    """Revisions, states and a shadow count in memory."""

    revisions: dict[int, StoredRevision] = field(default_factory=dict)
    rows: list[VersionState] = field(default_factory=list)
    shadow_count: int = 0

    async def revision(self, point: str, version: int, number: int) -> StoredRevision | None:
        """The stored revision."""
        return self.revisions.get(number)

    async def states(self, point: str) -> Sequence[VersionState]:
        """The stored states."""
        return list(self.rows)

    async def set_state(
        self, target: tuple[str, int, int, str], digest: str, note: str | None
    ) -> None:
        """Replace the version's state as the store would."""
        point, version, revision, state = target
        self.rows = [row for row in self.rows if row.version != version]
        self.rows.append(VersionState(point, version, state, revision, NOW))

    async def shadow_decisions(self, point: str, version: int, since: datetime) -> int:
        """The count the test set."""
        return self.shadow_count


def passing(number: int = 1, digest: str | None = None, *, passed: bool = True) -> StoredRevision:
    """A revision of the friction policy."""
    report = {} if passed else {"failures": ["ece:matches"]}
    return StoredRevision(
        "action.friction", 1, number, digest or ACTION_FRICTION.digest(), passed, report, NOW
    )


def promotion(admin: Admin, now: datetime = NOW) -> Promotion:
    """The service over the admin double at a fixed time."""
    return Promotion(admin, policies_by_key(), lambda: now)


async def test_a_passing_revision_goes_to_shadow() -> None:
    admin = Admin(revisions={1: passing()})

    refusal = await promotion(admin).promote(KEY, 1, "shadow", "first calibration")

    assert refusal is None
    assert [(row.state, row.revision) for row in admin.rows] == [("shadow", 1)]


async def test_a_revision_that_failed_or_fits_other_words_is_refused() -> None:
    admin = Admin(revisions={1: passing(passed=False), 2: passing(2, "f" * 16)})

    failed = await promotion(admin).promote(KEY, 1, "shadow", None)
    reworded = await promotion(admin).promote(KEY, 2, "shadow", None)
    missing = await promotion(admin).promote(KEY, 3, "shadow", None)
    unknown = await promotion(admin).promote("action.friction@9", 1, "shadow", None)

    assert failed is not None
    assert "ece:matches" in failed.reason
    assert reworded is not None
    assert missing is not None
    assert unknown is not None
    assert admin.rows == []


async def test_active_only_from_shadow_after_two_weeks_and_five_thousand_decisions() -> None:
    admin = Admin(revisions={1: passing()})

    straight = await promotion(admin).promote(KEY, 1, "active", None)
    await promotion(admin).promote(KEY, 1, "shadow", None)
    early = await promotion(admin, NOW + timedelta(days=13)).promote(KEY, 1, "active", None)
    admin.shadow_count = 4_999
    thin = await promotion(admin, NOW + timedelta(days=15)).promote(KEY, 1, "active", None)
    admin.shadow_count = 5_000
    ready = await promotion(admin, NOW + timedelta(days=15)).promote(KEY, 1, "active", None)

    assert straight is not None
    assert "тени" in straight.reason
    assert early is not None
    assert "две недели" in early.reason
    assert thin is not None
    assert "4999" in thin.reason
    assert ready is None
    assert [(row.state, row.revision) for row in admin.rows] == [("active", 1)]


async def test_an_active_version_takes_a_new_passing_revision_of_the_same_words() -> None:
    admin = Admin(revisions={1: passing(), 2: passing(2)})
    admin.rows = [VersionState("action.friction", 1, "active", 1, NOW)]

    refusal = await promotion(admin).promote(KEY, 2, "active", "refit")

    assert refusal is None
    assert [(row.state, row.revision) for row in admin.rows] == [("active", 2)]


async def test_retiring_takes_a_version_out_and_a_stranger_is_refused() -> None:
    admin = Admin(revisions={1: passing()})
    admin.rows = [VersionState("action.friction", 1, "active", 1, NOW)]

    refusal = await promotion(admin).retire(KEY, "rules again")
    never = await promotion(Admin()).retire(KEY, None)

    assert refusal is None
    assert [(row.state, row.revision) for row in admin.rows] == [("retired", 1)]
    assert never is not None
