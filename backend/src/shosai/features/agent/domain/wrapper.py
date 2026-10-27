"""Untrusted text in the model's context, and how much of it a run has seen (Leo §7.4).

Text Leo did not get from the person — a meeting's speech, a colleague's task, a web page, a
file — enters the context inside a wrapper: a boundary random per run, which the text's
author cannot know, and a label from a closed set, which is never the text's own words. The
text is escaped so it holds no `<<` at all: neither the opening nor the closing marker can
appear inside it, whatever it says. Every labelled result raises the run's taint, which only
grows: egress then needs a card, a write's card shows what it was prepared from, and memory
ignores a run whose text looked like an instruction to Leo.
"""

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Final

from shosai.core.agent_tools.context import Taint
from shosai.core.agent_tools.provenance import Provenance

BOUNDARY_BYTES: Final = 12
MCP_SERVER: Final = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")
_MARKER_START: Final = re.compile(r"<(?=<)")
_ESCAPED: Final = "< "
# Строка-маркер обёртки целиком: текст внутри экранирован и маркером стать не может.
_MARKER_LINE: Final = re.compile(r"^<<(?:untrusted source=[^>\n]+ |end )id=[0-9a-f]+>>\n?", re.M)


@dataclass(frozen=True, slots=True)
class Label:
    """Where wrapped text comes from: one of the closed set, never attacker text."""

    text: str

    @classmethod
    def of(cls, provenance: Provenance) -> Label:
        """The label of a slice's declared provenance."""
        return cls(provenance.value)

    @classmethod
    def mcp(cls, server: str) -> Label:
        """The label of an external MCP server's output, by the server's registered slug."""
        if not MCP_SERVER.fullmatch(server):
            message = "сервер MCP в метке — slug из латиницы, цифр, '_' и '-'"
            raise ValueError(message)
        return cls(f"mcp:{server}")


def boundary(entropy: bytes) -> str:
    """The run's boundary token from at least 12 random bytes."""
    if len(entropy) < BOUNDARY_BYTES:
        message = f"граница обёртки — не меньше {BOUNDARY_BYTES} случайных байт"
        raise ValueError(message)
    return entropy.hex()


def keyed_boundary(key: bytes, text: str) -> str:
    """A boundary for the stable head (segment 4): the same while the wrapped text is, so the
    provider's prefix cache holds, and unknowable without the server's key to whoever wrote the
    text — an HMAC of it (ADR 0071 MM-D7)."""
    return hmac.new(key, text.encode(), hashlib.sha256).hexdigest()[: BOUNDARY_BYTES * 2]


def opening(label: Label, token: str) -> str:
    """The marker before wrapped text."""
    return f"<<untrusted source={label.text} id={token}>>"


def closing(token: str) -> str:
    """The marker after wrapped text."""
    return f"<<end id={token}>>"


def escape(text: str) -> str:
    """The text with every `<` that starts a `<<` spaced out, so no marker can form in it."""
    return _MARKER_START.sub(_ESCAPED, text)


def wrap(text: str, label: Label, token: str) -> str:
    """Untrusted text between its markers, escaped, each marker on its own line."""
    return f"{opening(label, token)}\n{escape(text)}\n{closing(token)}"


def unwrapped(text: str) -> str:
    """Wrapped text without its marker lines: the pieces as written, for a judge to read."""
    return _MARKER_LINE.sub("", text).strip("\n")


def taint_after(current: Taint, label: Label | None, *, instructions_seen: bool = False) -> Taint:
    """The run's taint after a result: any labelled text is external, never less than before.

    `instructions_seen` is the `content.injection` judgement (decisions): text addressed to
    an AI assistant makes the run suspicious.
    """
    level = Taint.NONE if label is None else Taint.EXTERNAL
    if instructions_seen:
        level = Taint.SUSPICIOUS
    return max(current, level)


def egress_needs_card(taint: Taint) -> bool:
    """Whether sending data out (web search, external MCP) waits for the person's card."""
    return taint >= Taint.EXTERNAL
