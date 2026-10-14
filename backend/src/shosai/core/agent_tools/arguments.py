"""Arguments of a tool call, validated against the spec's input model (ADR 0029 point 3).

The model's JSON is parsed by the input model; anything that does not fit becomes an
`invalid_arguments` error naming the fields, never their values, which the model reads and
corrects (the draft turned invalid JSON into `{}` and ran the tool). The agent rejects a
call whose JSON was cut by `finish_reason=length` before it gets here.
"""

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, ValidationError

from shosai.core.agent_tools.results import ToolError, ToolErrorCode
from shosai.core.agent_tools.spec import ToolSpec

MAX_LISTED_FIELDS: Final = 10
WHOLE_INPUT: Final = "(arguments)"


def parse_arguments[I: BaseModel, O: BaseModel](
    spec: ToolSpec[I, O], raw: str | bytes | Mapping[str, object]
) -> I | ToolError:
    """The call's arguments as the input model, or the error the model can act on."""
    try:
        if isinstance(raw, Mapping):
            return spec.input.model_validate(raw, strict=False)
        return spec.input.model_validate_json(raw)
    except ValidationError as invalid:
        return ToolError(ToolErrorCode.INVALID_ARGUMENTS, {"fields": failed_fields(invalid)})


def failed_fields(invalid: ValidationError) -> str:
    """The paths of the failed fields, comma-separated, without the submitted values."""
    paths: list[str] = []
    for error in invalid.errors(include_input=False, include_url=False):
        path = ".".join(str(part) for part in error["loc"]) or WHOLE_INPUT
        if path not in paths:
            paths.append(path)
    return ", ".join(paths[:MAX_LISTED_FIELDS])
