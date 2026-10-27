"""`voice.approval@1`: whether a spoken reply approves the card just read back (Leo §8.4; the
owner's bounded exception of 2026-10-27, ADR 0069).

Leo reads a reversible or compensable card aloud and the person answers. This policy reads
the answer: is it a clear yes to carrying out exactly that action now? It is the one point
that reads a person's consent, so its outcome may be less careful than the rule's "not
given": the engine returns it only from an active version's answer in time — never from a
shadow, a late answer or a fallback — counts every consent, and pages should a changed
outcome ever leave another way. A yes is fitted for 99 % precision; an unsure answer is no.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from typing import Final

from shosai.core.ai.decisions import NoulQuestion, Question
from shosai.features.decisions.domain.calibration import Aims, CutAim
from shosai.features.decisions.domain.case_fields import text
from shosai.features.decisions.domain.policy import Policy, question_text
from shosai.features.decisions.domain.state import Fact, TextField, build_state
from shosai.features.decisions.domain.verdicts import Signal, Verdict

APPROVES: Final = "approves"
READ_BACK_TOKENS: Final = 500
REPLY_TOKENS: Final = 120

APPROVES_QUESTION: Final = NoulQuestion(
    instructions=(
        "Decide whether the user's spoken reply, said right after the assistant read a "
        "proposed action aloud, clearly approves carrying out exactly that action now."
    ),
    when_true=(
        "The reply clearly says yes to doing this action now, as it was read, without "
        "changing it, adding a condition or another request, or asking something first."
    ),
    when_false=(
        "The reply refuses, hesitates, asks a question, changes the action or its details, "
        "adds a condition or another request, is about something else, breaks off before "
        "it is finished, or is unclear."
    ),
)


class VoiceConsent(IntEnum):
    """Whether the person's words gave consent; a higher value is more careful."""

    GIVEN = 0
    NOT_GIVEN = 1


@dataclass(frozen=True, slots=True)
class VoiceFacts:
    """The card as Leo read it aloud, and the reply as the server heard it."""

    read_back: str
    utterance: str


class VoiceApproval(Policy[VoiceFacts, VoiceConsent]):
    """Version 1: consent only when the reply is surely a clear yes."""

    point = "voice.approval"
    version = 1
    # Человек ждёт ответа голосом: короче этого Jev не уложится, дольше — пауза в разговоре.
    deadline = timedelta(milliseconds=800)
    cuts = (APPROVES,)
    reads_consent = True
    aims = Aims(
        cuts={APPROVES: CutAim(Verdict.YES, precision=0.99, unsure_joins=Verdict.NO)},
        margin=0.05,
        accuracy_floor=0.9,
        # Случай «нет» должен остаться «нет» почти всегда: ложное «да» исполняет действие.
        careful_floor=0.99,
    )

    def settled(self, facts: VoiceFacts, rule: VoiceConsent) -> bool:
        """An empty reply gives nothing."""
        return not facts.utterance.strip()

    def questions(self, facts: VoiceFacts) -> Mapping[str, Question]:
        """Whether the reply approves the action."""
        return {APPROVES: APPROVES_QUESTION}

    def signals(self, facts: VoiceFacts) -> Mapping[str, Signal]:
        """The probability as is."""
        return {APPROVES: Signal(APPROVES)}

    def state(self, facts: VoiceFacts) -> dict[str, object]:
        """The card as read aloud and the reply."""
        texts = {
            "read_back": TextField(facts.read_back, READ_BACK_TOKENS),
            "reply": TextField(facts.utterance, REPLY_TOKENS),
        }
        return build_state({}, texts, self.budget)

    def facts(self, facts: VoiceFacts) -> Mapping[str, Fact]:
        """How long the card and the reply were: numbers, never their words."""
        return {
            "read_back_lines": len(facts.read_back.splitlines()),
            "reply_words": len(facts.utterance.split()),
        }

    def outcome(
        self, facts: VoiceFacts, verdicts: Mapping[str, Verdict], chances: Mapping[str, float]
    ) -> VoiceConsent:
        """Given only when the answer is surely yes."""
        if verdicts.get(APPROVES, Verdict.UNSURE) is Verdict.YES:
            return VoiceConsent.GIVEN
        return VoiceConsent.NOT_GIVEN

    def careful(self, rule: VoiceConsent, judged: VoiceConsent) -> VoiceConsent:
        """The judged consent: the rule's "not given" is the default, not a floor."""
        return judged

    def less_careful(self, value: VoiceConsent, rule: VoiceConsent) -> bool:
        """A consent given where the rule gives none."""
        return value < rule

    def code(self, value: VoiceConsent) -> str:
        """`given` or `not_given`."""
        return value.name.lower()

    def parse_facts(self, raw: Mapping[str, object]) -> VoiceFacts:
        """A read-back and a reply from a dataset case."""
        return VoiceFacts(read_back=text(raw, "read_back"), utterance=text(raw, "utterance"))

    def careful_case(self, expected: VoiceConsent) -> bool:
        """A reply that must not approve."""
        return expected is VoiceConsent.NOT_GIVEN

    def wording(self) -> Mapping[str, object]:
        """The one question."""
        return {APPROVES: question_text(APPROVES_QUESTION)}


VOICE_APPROVAL: Final = VoiceApproval()
