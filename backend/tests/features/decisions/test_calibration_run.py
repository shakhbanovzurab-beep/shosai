"""A calibration run: live answers recorded beside the sets, a recorded run re-read without a
call, a revision stored and its report written beside the run either way (Leo §6.4, DL-D6)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shosai.core.ai.calls import CallContext, CallOrigin, ModelRoute, PlatformAccount
from shosai.core.ai.decisions import Decision, DecisionRequest
from shosai.core.ai.results import Usage
from shosai.features.decisions.application.calibration import Calibration
from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from shosai.features.decisions.infrastructure.datasets import (
    RECORDED,
    read_recorded,
    read_report,
    read_sets,
    report_data,
)
from tests.features.decisions.engine_bench import JEV, ScriptedJev
from tests.features.decisions.sets_bench import (
    answers_for,
    friction_sets,
    index_of,
    labels_of,
    write_sets,
)


@dataclass
class Revisions:
    """Stored revisions in memory."""

    stored: list[tuple[str, int, str, tuple[Mapping[str, Any], Mapping[str, Any], bool]]] = field(
        default_factory=list
    )

    async def add_revision(
        self,
        point: str,
        version: int,
        digest: str,
        fitted: tuple[Mapping[str, Any], Mapping[str, Any], bool],
    ) -> int:
        """Keep it; its number."""
        self.stored.append((point, version, digest, fitted))
        return len(self.stored)


class CaseJev(ScriptedJev):
    """Answers each case as its labels lean; the case is read back from its request."""

    async def decide(
        self, context: CallContext, route: ModelRoute, request: DecisionRequest
    ) -> Decision:
        """The leaning answer of the case whose state this is; nothing shared between calls."""
        self.asked.append((context, request))
        state = request.state
        assert isinstance(state, Mapping)
        index = index_of(str(state["request"]))
        answers = answers_for(labels_of(index), lean=0.49, index=index)
        return Decision(
            answers, JEV, "typesafe/jev-1.13-20260917", "gen-1", Usage(input_tokens=600)
        )


async def test_a_live_run_is_recorded_then_re_read_without_a_call(tmp_path: Path) -> None:
    synthetic, reference = friction_sets(per_language=160, reference=60)
    write_sets(tmp_path, synthetic, reference)
    folder = tmp_path / "action_friction"
    jev, revisions = CaseJev(), Revisions()
    calibration = Calibration(revisions, (jev, ModelRoute(JEV)), tmp_path)

    live = await calibration.run(ACTION_FRICTION, live=True, concurrency=8)
    asked = len(jev.asked)
    again = await calibration.run(ACTION_FRICTION, live=False, concurrency=8)

    total = len(read_sets(ACTION_FRICTION, tmp_path).synthetic) + 120
    assert asked == total
    assert len(jev.asked) == asked
    assert (live.report.failures, again.report.failures) == ((), ())
    assert (live.revision, again.revision, live.unanswered) == (1, 2, 0)
    assert len(read_recorded(ACTION_FRICTION, tmp_path)) == total
    assert (folder / RECORDED).exists()
    context = jev.asked[0][0]
    assert (context.origin, context.platform_account) == (CallOrigin.SYSTEM, PlatformAccount.SYSTEM)
    point, version, digest, (cuts, numbers, passed) = revisions.stored[0]
    assert (point, version, digest, passed) == (
        "action.friction",
        1,
        ACTION_FRICTION.digest(),
        True,
    )
    assert set(cuts) == {"matches", "wide"}
    assert numbers["failures"] == []
    assert read_report(ACTION_FRICTION, tmp_path) == report_data(ACTION_FRICTION, again.report)


async def test_a_failing_run_is_reported_as_it_failed(tmp_path: Path) -> None:
    synthetic, _ = friction_sets(per_language=160, reference=0)
    write_sets(tmp_path, synthetic, [])
    calibration = Calibration(Revisions(), (CaseJev(), ModelRoute(JEV)), tmp_path)

    run = await calibration.run(ACTION_FRICTION, live=True, concurrency=8)

    report = read_report(ACTION_FRICTION, tmp_path)
    assert report is not None
    assert (report["passed"], report["policy"]) == (False, "action.friction@1")
    assert report["failures"] == list(run.report.failures)
    assert any(failure.startswith("reference") for failure in report["failures"])


async def test_a_reworded_policy_never_reuses_a_recorded_run(tmp_path: Path) -> None:
    synthetic, reference = friction_sets(per_language=2, reference=1)
    write_sets(tmp_path, synthetic, reference)
    (tmp_path / "action_friction" / RECORDED).write_text(
        '{"id": "ru-0", "digest": "0000000000000000", "snapshot": "s", "answers": {}}\n',
        encoding="utf-8",
    )

    assert read_recorded(ACTION_FRICTION, tmp_path) == {}
