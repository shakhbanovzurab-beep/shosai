"""An action as the cabinet's card reads it, in the stream and over HTTP (agent step 9a).

The card carries what the person decides with: the action's id and nonce, its public status,
the tool, whether it asks for a careful decision on the screen, what the run read before it
(labels), how it can be undone, its times, and an item's code when it did not succeed. Step 9b
adds the words — title, space and fields — that each slice renders in the person's language.
"""

from pydantic import JsonValue

from shosai.features.agent.application.action_rows import items_of
from shosai.features.agent.domain.action_items import ItemState
from shosai.features.agent.domain.actions import ActionStatus, public_status
from shosai.features.agent.domain.friction import Friction, screen_only
from shosai.features.agent.infrastructure.run_records import AgentActionRecord


def action_card(record: AgentActionRecord) -> dict[str, JsonValue]:
    """The card of an action."""
    items = items_of(record)
    first = items[0]
    codes = [item.code for item in items if item.state is not ItemState.SUCCEEDED and item.code]
    return {
        "id": str(record.id),
        "tool": first.tool,
        "status": public_status(ActionStatus(record.status)).value,
        "outcome": codes[0] if codes else None,
        "nonce": record.nonce,
        "warning": screen_only(Friction(record.friction)),
        "taint": record.taint_sources[0] if record.taint_sources else None,
        "reversibility": first.reversibility,
        "created_at": record.created_at.isoformat(),
        "expires_at": record.expires_at.isoformat(),
        "resolved_at": None if record.resolved_at is None else record.resolved_at.isoformat(),
    }
