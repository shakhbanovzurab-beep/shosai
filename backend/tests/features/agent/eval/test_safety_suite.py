"""The safety suite CI runs on every push (agent step 8; Leo §7.4, §11.4).

Every payload of the corpus goes through every channel of untrusted text — each read tool
whose result someone else wrote, and the page's meeting, task and file — and a model obeys
it: no write runs, nothing leaves the cabinet, the run is tainted and the text stays wrapped.
"""

import pytest

from shosai.features.agent.application.eval_runner import EvalRunner
from shosai.features.agent.application.eval_suites import safety_problems
from shosai.features.agent.domain.eval_cases import InjectionCarrier
from shosai.features.agent.infrastructure.eval_files import load_corpus

CORPUS = load_corpus()


@pytest.mark.parametrize("carrier", CORPUS.carriers, ids=lambda carrier: carrier.channel)
async def test_hostile_text_through_a_channel_changes_nothing_and_stays_wrapped(
    eval_runner: EvalRunner, carrier: InjectionCarrier
) -> None:
    channel = CORPUS.model_copy(update={"carriers": (carrier,)})

    found = await safety_problems(eval_runner, channel)

    assert {case: problems for case, problems in found.items() if problems} == {}
    assert len(found) == len(CORPUS.payloads)
