"""The state Jev reads: typed facts and named text fields, within a budget (Leo §6.1, §6.2).

The state is JSON. Facts are numbers, booleans and short codes computed in code — Jev is
weak at counting and arithmetic, so it is never asked to derive them. Text goes into string
fields named for what they hold (`request`, `card`, `text`); JSON's escaping keeps every
piece inside its field, so no marker can be forged and the field's name is its provenance.
Each field is cut to its own share of tokens, head and tail kept; the whole state stays
within the policy's budget (≈ 2 000 tokens by default).
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

# Как у агента: не больше трёх байт UTF-8 на токен — оценка сверху для любого языка.
BYTES_PER_TOKEN: Final = 3
DEFAULT_BUDGET: Final = 2_000
CUT_MARK: Final = "\n[...]\n"
# Символы, которые JSON пишет двумя байтами (\" \\ \b \f \n \r \t), и прочие управляющие.
_TWO_BYTE_ESCAPES: Final = frozenset('"\\\b\f\n\r\t')
CONTROL_LIMIT: Final = 0x20
UNICODE_ESCAPE_SIZE: Final = 6

type Fact = bool | int | float | str


def tokens_of(text: str) -> int:
    """Tokens of a text, estimated from above; a lone surrogate counts as a replacement."""
    return math.ceil(len(text.encode("utf-8", "replace")) / BYTES_PER_TOKEN)


def clip(text: str, tokens: int) -> str:
    """The text within `tokens` as JSON writes it: whole, or its head and tail around a cut
    mark. Escapes count, so quotes or backslashes cannot push the state over its budget."""
    text = well_formed(text)
    size = tokens * BYTES_PER_TOKEN
    if escaped_size(text) <= size:
        return text
    room = max(size - escaped_size(CUT_MARK), 0)
    head = cut_escaped(text, room // 2 + room % 2)
    tail = cut_escaped(text[::-1], room // 2)[::-1]
    return f"{head}{CUT_MARK}{tail}"


def well_formed(text: str) -> str:
    """The text with lone surrogates replaced: they have no UTF-8 and would break the call."""
    return text.encode("utf-8", "replace").decode("utf-8")


def char_size(char: str) -> int:
    """The bytes JSON writes for one character (`ensure_ascii=False`)."""
    if char in _TWO_BYTE_ESCAPES:
        return 2
    if ord(char) < CONTROL_LIMIT:
        return UNICODE_ESCAPE_SIZE
    return len(char.encode())


def escaped_size(text: str) -> int:
    """The UTF-8 bytes of the text inside a JSON string, quotes excluded."""
    return sum(char_size(char) for char in text)


def cut_escaped(text: str, size: int) -> str:
    """The longest start of the text whose escaped UTF-8 fits in `size` bytes."""
    used = 0
    for index, char in enumerate(text):
        used += char_size(char)
        if used > size:
            return text[:index]
    return text


@dataclass(frozen=True, slots=True)
class TextField:
    """A text the state carries and its share of the budget."""

    text: str
    tokens: int


def build_state(
    facts: Mapping[str, Fact], texts: Mapping[str, TextField], budget: int = DEFAULT_BUDGET
) -> dict[str, object]:
    """The state: `facts`, then each text field cut to its share; refuses one over budget."""
    state: dict[str, object] = {"facts": dict(facts)}
    for name, field in texts.items():
        if name == "facts":
            message = "текстовое поле не может называться facts"
            raise ValueError(message)
        state[name] = clip(field.text, field.tokens)
    if state_tokens(state) > budget:
        message = "состояние решения больше своего бюджета"
        raise ValueError(message)
    return state


def state_tokens(state: Mapping[str, object]) -> int:
    """The state's tokens as Jev reads it, in JSON."""
    return tokens_of(state_json(state))


def state_json(state: Mapping[str, object]) -> str:
    """The state's canonical JSON: sorted keys, no spaces, the same bytes for the same state."""
    return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
