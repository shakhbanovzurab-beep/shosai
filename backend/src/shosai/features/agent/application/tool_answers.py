"""What the model reads back for a call: a result, a digest, an error or a refusal (step 6).

Everything here is JSON the model reads as a prompt, so every word in it is registered English
text: the tools' own error texts, the agent's refusals and the digest's note. A result over its
budget becomes a digest naming its `result_ref`; a step shows the one argument its tool names.
"""

from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, JsonValue

from shosai.core.agent_tools.results import ToolError
from shosai.core.agent_tools.spec import ToolSpec
from shosai.core.ai.requests import ToolCall
from shosai.features.agent.application.run_work import DETAIL_MAX
from shosai.features.agent.domain.budgets import estimate_tokens
from shosai.features.agent.domain.digests import compact, digest
from shosai.features.agent.infrastructure.prompts import CUT_RESULT

# Запас на конверт дайджеста сверх его оценки: ссылка, флаги, имена урезанных списков.
ENVELOPE_SPARE: Final = 40


def error_content(error: ToolError) -> str:
    """A tool's typed error, with its registered text and its parameters."""
    return compact({"error": {"code": error.code.value, "message": error.text, **error.params}})


def refusal_content(code: str, text: str) -> str:
    """The agent's refusal of a call that did not run."""
    return compact({"error": {"code": code, "message": text}})


def digest_content(value: JsonValue, budget: int, ref: UUID, cites: list[JsonValue]) -> str:
    """A result cut to its budget, with the ref of the whole and its sources whole; the
    skeleton only when even the cut does not fit."""
    envelope: dict[str, JsonValue] = {"truncated": True, "result_ref": str(ref), "note": CUT_RESULT}
    if cites:
        envelope["sources"] = cites
    room = budget - estimate_tokens(compact(envelope)) - ENVELOPE_SPARE
    cut = digest(value, room) if room > 0 else None
    if cut is not None:
        envelope |= {"omitted": dict(cut.omitted), "result": cut.value}
    return compact(envelope)


def step_detail(spec: ToolSpec[Any, Any], arguments: BaseModel) -> str | None:
    """The argument a step shows, cut short; None when the tool names none."""
    if spec.step_detail is None:
        return None
    value = getattr(arguments, spec.step_detail, None)
    if not isinstance(value, str | int) or isinstance(value, bool) or value == "":
        return None
    text = str(value)
    return text if len(text) <= DETAIL_MAX else text[: DETAIL_MAX - 1] + "…"


def named(call: ToolCall, round_number: int, index: int) -> ToolCall:
    """The call with an id: a provider that sent none gets one, so its answer can name it."""
    if call.call_id:
        return call
    return ToolCall(f"leo-{round_number}-{index}", call.name, call.arguments)
