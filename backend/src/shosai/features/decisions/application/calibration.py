"""A calibration run: Jev's answers to a point's sets, the fitted cuts, the gates, a revision
(Leo §6.4, ADR 0069 DL-D6, DL-D8).

Live, every case of the synthetic and the reference set is asked as the platform's own call
— the cases hold no person's data — a few at a time, and the answers are written as the
point's recorded run. From a recorded run, nothing is asked. Either way the cuts are fitted,
every gate is checked, and the result is stored as the version's next revision, passing or
not, with a report of numbers only.
"""

import asyncio
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Final, Protocol

import structlog

from shosai.core.ai.calls import CallClass, CallContext, CallOrigin, ModelRoute, PlatformAccount
from shosai.core.ai.decisions import Answer, DecisionRequest
from shosai.core.ai.errors import AiCallError
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.features.decisions.application.asking import JevPort
from shosai.features.decisions.domain.examples import Case
from shosai.features.decisions.domain.gates import Report, calibrated
from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.infrastructure.datasets import (
    DATASETS,
    answered,
    read_recorded,
    read_sets,
    write_recorded,
)
from shosai.features.decisions.infrastructure.policy_store import cuts_json

CALL_DEADLINE: Final = timedelta(seconds=10)
log = structlog.stdlib.get_logger(__name__)


class Revisions(Protocol):
    """Where a calibration's revision is kept."""

    async def add_revision(
        self,
        point: str,
        version: int,
        digest: str,
        fitted: tuple[Mapping[str, Any], Mapping[str, Any], bool],
    ) -> int:
        """Store a revision; its number."""
        ...


@dataclass(frozen=True, slots=True)
class Calibrated:
    """A run's report, the revision it was stored as, and how many cases had no answer."""

    report: Report
    revision: int
    unanswered: int


class Calibration:
    """Calibrates a policy version on its sets."""

    def __init__(
        self, revisions: Revisions, jev: tuple[JevPort, ModelRoute], root: Path = DATASETS
    ) -> None:
        self._revisions = revisions
        self._jev, self._route = jev
        self._root = root

    async def run(self, policy: Policy[Any, Any], *, live: bool, concurrency: int) -> Calibrated:
        """Answer (or re-read) every case, fit, gate and store the revision."""
        sets = read_sets(policy, self._root)
        cases = (*sets.synthetic, *sets.reference)
        if live:
            answers, snapshot = await self._ask_all(policy, cases, concurrency)
            write_recorded(policy, snapshot, answers, self._root)
        recorded = read_recorded(policy, self._root)
        synthetic = answered(sets.synthetic, recorded)
        reference = answered(sets.reference, recorded)
        report = calibrated(policy, synthetic, reference, SUPPORTED_LANGUAGES)
        numbers = dict(report.numbers) | {"failures": list(report.failures)}
        revision = await self._revisions.add_revision(
            policy.point, policy.version, policy.digest(),
            (cuts_json(report.cuts), numbers, report.passed),
        )  # fmt: skip
        unanswered = len(cases) - len(synthetic) - len(reference)
        return Calibrated(report, revision, unanswered)

    async def _ask_all(
        self, policy: Policy[Any, Any], cases: Sequence[Case], concurrency: int
    ) -> tuple[dict[str, Mapping[str, Answer]], str]:
        """Every case's answers; a case Jev did not answer is left out and logged."""
        gate = asyncio.Semaphore(concurrency)
        run = uuid.uuid4().hex[:12]
        answers: dict[str, Mapping[str, Answer]] = {}
        snapshots: set[str] = set()

        async def ask(case: Case) -> None:
            async with gate:
                request = DecisionRequest(policy.state(case.facts), policy.questions(case.facts))
                context = CallContext(
                    effect_key=f"calibration:{run}:{policy.key}:{case.id}"[:200],
                    feature="decisions.calibration",
                    call_class=CallClass.STANDARD,
                    origin=CallOrigin.SYSTEM,
                    platform_account=PlatformAccount.SYSTEM,
                    deadline=CALL_DEADLINE,
                )
                try:
                    decision = await self._jev.decide(context, self._route, request)
                except AiCallError as error:
                    log.warning(
                        "Случай калибровки без ответа", case=case.id, failure=error.failure.value
                    )
                    return
                answers[case.id] = decision.answers
                snapshots.add(decision.snapshot)

        await asyncio.gather(*(ask(case) for case in cases))
        if len(snapshots) > 1:
            log.warning("Прогон калибровки ответили разные снимки Jev", snapshots=sorted(snapshots))
        return answers, ",".join(sorted(snapshots))
