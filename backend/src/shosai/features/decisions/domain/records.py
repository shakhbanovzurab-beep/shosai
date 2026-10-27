"""A decision's record: ids, numbers and codes, never text (Leo §6.5, ADR 0069 DL-D7).

The record holds no person's id and no text: the subject by id, the facts as numbers and
codes, a keyed hash of the state (so identical states can be told apart in replay without
the state being recoverable from its hash), the probabilities, the rule's outcome beside the
final one, why and from where. It expires with its monthly partition. The cost is the
provider port's row for the effect key `decision:<id>`, not a column here.
"""

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final
from uuid import UUID

from shosai.features.decisions.domain.outcomes import DecisionReason, DecisionSource, Subject
from shosai.features.decisions.domain.state import Fact

STATE_HASH_BYTES: Final = 16
EFFECT_PREFIX: Final = "decision:"


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """One consulted decision, as `agent_decisions` keeps it."""

    id: UUID
    created_at: datetime
    point: str
    version: int
    revision: int | None
    shadow: bool
    subject: Subject
    language: str
    facts: Mapping[str, Fact]
    rule_outcome: str
    outcome: str
    reason: DecisionReason
    source: DecisionSource
    latency_ms: int
    state_hash: bytes | None = None
    probabilities: Mapping[str, float] = field(default_factory=dict)
    jev_snapshot: str | None = None
    jev_request_id: str | None = None


def state_hash(state_json: str, key: bytes) -> bytes:
    """The state's keyed hash: equal states match, the state cannot be guessed back."""
    if not key:
        message = "ключ хеша состояния не может быть пустым"
        raise ValueError(message)
    digest = hmac.new(key, state_json.encode("utf-8", "replace"), hashlib.sha256).digest()
    return digest[:STATE_HASH_BYTES]


def effect_key(decision_id: UUID) -> str:
    """The provider port's effect key of a decision's Jev call: one cost row per decision."""
    return f"{EFFECT_PREFIX}{decision_id}"
