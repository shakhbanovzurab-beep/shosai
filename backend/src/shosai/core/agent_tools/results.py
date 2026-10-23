"""What a tool hands back: a planned effect, a preview, a result or a typed error.

`PlannedEffect` freezes the exact targets of a write when it is proposed; `execute` applies
the effect to those targets only, so the preview and the execution cannot diverge (Leo
§8.1, audit A8). A `Preview` is an i18n key with parameters: the server writes it, never
the model. A `ToolResult` is the output model or a `ToolError` whose code the model can
explain; the error's text is the code's registered English text, never a slice's prose,
so everything a model reads from a failed tool is in the model-facing test. A result also
names its sources and the artifacts it hands over (`core.agent_tools.sources`, ADR 0068).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, JsonValue

from shosai.core.agent_tools.sources import ArtifactRef, SourceRef

type PreviewParam = str | int | float | bool | None
type ErrorParam = str | int | bool


class ToolErrorCode(StrEnum):
    """Why a call gave no result; a closed set the model and the agent both know."""

    INVALID_ARGUMENTS = "invalid_arguments"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    NOT_ENTITLED = "not_entitled"
    LIMIT_REACHED = "limit_reached"
    SWITCHED_OFF = "switched_off"
    CONFLICT = "conflict"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"


# Модель читает эти тексты как результат инструмента: только английский (CLAUDE.md, Prompts).
TOOL_ERROR_TEXTS: Final[Mapping[ToolErrorCode, str]] = {
    ToolErrorCode.INVALID_ARGUMENTS: (
        "The arguments do not match the tool's schema. Fix the fields listed and call again."
    ),
    ToolErrorCode.NOT_FOUND: "Nothing was found for these arguments; it may have been deleted.",
    ToolErrorCode.FORBIDDEN: "The user has no access to this. Do not retry; tell the user.",
    ToolErrorCode.NOT_ENTITLED: "The user's plan does not include this tool. Tell the user.",
    ToolErrorCode.LIMIT_REACHED: (
        "This would go over a limit of the user's plan. Do not retry; tell the user what "
        "they can free up or that a larger plan allows it."
    ),
    ToolErrorCode.SWITCHED_OFF: "The user turned this tool off in settings. Do not retry.",
    ToolErrorCode.CONFLICT: "The data changed since it was read. Read it again before acting.",
    ToolErrorCode.TIMEOUT: "The tool did not answer in time. Retry once at most.",
    ToolErrorCode.UNAVAILABLE: "The service behind this tool is unavailable. Try again later.",
    ToolErrorCode.RATE_LIMITED: "Too many calls of this tool. Wait before calling it again.",
    ToolErrorCode.FAILED: "The tool failed. Do not retry; tell the user it did not work.",
}


@dataclass(frozen=True, slots=True)
class ToolError:
    """A typed failure: the code, and parameters such as the fields that failed validation."""

    code: ToolErrorCode
    params: Mapping[str, ErrorParam] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """What the model reads."""
        return TOOL_ERROR_TEXTS[self.code]


@dataclass(frozen=True, slots=True)
class ToolResult[O: BaseModel]:
    """The output of a call, or its error; exactly one of them.

    An output may name the sources it rests on and the artifacts it hands over; an error
    has neither.
    """

    output: O | None = None
    error: ToolError | None = None
    sources: tuple[SourceRef, ...] = ()
    artifacts: tuple[ArtifactRef, ...] = ()

    def __post_init__(self) -> None:
        if (self.output is None) == (self.error is None):
            message = "результат инструмента — либо данные, либо ошибка"
            raise ValueError(message)
        if self.error is not None and (self.sources or self.artifacts):
            message = "у ошибки инструмента нет источников и артефактов"
            raise ValueError(message)

    @classmethod
    def failed(cls, code: ToolErrorCode, **params: ErrorParam) -> ToolResult[O]:
        """A result that is the error of the code."""
        return cls(error=ToolError(code, params))


@dataclass(frozen=True, slots=True)
class PlannedEffect:
    """A write as proposed: the exact targets and what the slice needs to apply it.

    `data` is JSON, since the agent keeps the plan in its action row until approval; the
    slice reads it back with its own model in `execute`.
    """

    targets: tuple[str, ...]
    data: Mapping[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Preview:
    """The server's account of a planned write: an i18n key the cabinet renders."""

    key: str
    params: Mapping[str, PreviewParam] = field(default_factory=dict)
