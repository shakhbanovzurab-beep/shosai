"""The policies of this slice's decision points, one version each (ADR 0069).

Each point's later versions join here beside the one in force, so a shadow version can run
next to it; their question texts are registered in the model-facing English test through
`policy_wording`.
"""

from collections.abc import Mapping
from typing import Any, Final

from shosai.features.decisions.domain.policies.action_friction import ACTION_FRICTION
from shosai.features.decisions.domain.policies.content_injection import CONTENT_INJECTION
from shosai.features.decisions.domain.policies.turn_route import TURN_ROUTE
from shosai.features.decisions.domain.policies.voice_approval import VOICE_APPROVAL
from shosai.features.decisions.domain.policy import Policy, check_point

POLICIES: Final[tuple[Policy[Any, Any], ...]] = (
    TURN_ROUTE, ACTION_FRICTION, CONTENT_INJECTION, VOICE_APPROVAL,
)  # fmt: skip


def policies_by_key() -> dict[str, Policy[Any, Any]]:
    """Every policy by `point@version`; refuses a key declared twice or a malformed point."""
    found: dict[str, Policy[Any, Any]] = {}
    for policy in POLICIES:
        check_point(policy.point)
        if policy.key in found:
            message = f"политика объявлена дважды: {policy.key}"
            raise ValueError(message)
        found[policy.key] = policy
    return found


def policy_wording() -> Mapping[str, Mapping[str, object]]:
    """What Jev reads of every policy's questions, by `point@version`."""
    return {policy.key: policy.wording() for policy in POLICIES}
