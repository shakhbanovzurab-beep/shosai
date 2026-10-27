"""The policies in force and their cuts, read from the EU home (decisions plan §3.6).

One read returns every version in shadow or active with the threshold revision it names. A
revision whose cuts do not parse is skipped and logged: a policy without valid cuts is not
in force, so its point runs its rule.
"""

from collections.abc import Mapping, Sequence

import structlog
from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError

from shosai.core.db.errors import HomeUnavailableError
from shosai.core.db.transactions import HomeTransactions
from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.features.decisions.application.in_force import PoliciesUnreadableError, StoredPolicy
from shosai.features.decisions.domain.verdicts import Cut
from shosai.features.decisions.infrastructure.records import PolicyStateRow, ThresholdRevisionRow

POLICY = PolicyStateRow
REVISION = ThresholdRevisionRow
IN_FORCE = (
    select(
        POLICY.point, POLICY.version, POLICY.state, POLICY.revision, POLICY.questions_digest,
        REVISION.cuts,
    )
    .join(
        REVISION,
        and_(
            REVISION.point == POLICY.point,
            REVISION.version == POLICY.version,
            REVISION.revision == POLICY.revision,
        ),
    )
    .where(POLICY.state.in_(("active", "shadow")))
)  # fmt: skip
log = structlog.stdlib.get_logger(__name__)


class PolicyStore:
    """Reads the policies in force from the EU home."""

    def __init__(self, transactions: HomeTransactions) -> None:
        self._transactions = transactions

    async def in_force(self) -> Sequence[StoredPolicy]:
        """Every version in shadow or active, with valid cuts."""
        try:
            async with self._transactions.begin(TenancyScope(Home.EU), read_only=True) as session:
                rows = (await session.execute(IN_FORCE)).all()
        except (SQLAlchemyError, HomeUnavailableError) as error:
            raise PoliciesUnreadableError(type(error).__name__) from error
        found: list[StoredPolicy] = []
        for point, version, state, revision, digest, raw in rows:
            cuts = parsed_cuts(raw)
            if cuts is None:
                log.error("Пороги ревизии не читаются", point=point, version=version)
                continue
            found.append(StoredPolicy(point, version, state, revision, digest, cuts))
        return found


def parsed_cuts(raw: object) -> dict[str, Cut] | None:
    """`{"name": {"lower": .., "upper": ..}}` as cuts; None when anything is off."""
    if not isinstance(raw, dict):
        return None
    cuts: dict[str, Cut] = {}
    for name, edges in raw.items():
        cut = parsed_cut(edges)
        if cut is None:
            return None
        cuts[str(name)] = cut
    return cuts


def parsed_cut(edges: object) -> Cut | None:
    """One cut's edges, or None."""
    if not isinstance(edges, dict):
        return None
    lower, upper = number(edges.get("lower")), number(edges.get("upper"))
    if lower is None or upper is None:
        return None
    try:
        return Cut(lower=lower, upper=upper)
    except ValueError:
        return None


def number(raw: object) -> float | None:
    """A JSON number as a float; anything else is None."""
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return None
    return float(raw)


def cuts_json(cuts: Mapping[str, Cut]) -> dict[str, dict[str, float]]:
    """Cuts as a revision stores them."""
    return {name: {"lower": cut.lower, "upper": cut.upper} for name, cut in cuts.items()}
