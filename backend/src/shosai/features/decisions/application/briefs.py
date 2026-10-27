"""What the generator is asked to write for each point, with labels set by construction (DL-D8).

The code chooses each case's labels and the facts it fixes — a tool, a count of items, the
tool sets offered, the kind of text — in a deterministic rotation, so every label value and
every kind is covered evenly; the generator only writes the text that makes the labels true.
A case it writes is kept only when the blind labeller agrees with those labels.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from shosai.features.decisions.domain.examples import Label
from shosai.features.decisions.infrastructure.generation_texts import (
    FRICTION_MATCH,
    FRICTION_REACH,
    INJECTION_KINDS,
    INJECTION_PATTERNS,
    INJECTION_SEEN,
    ROUTE_TOOLSETS,
    TEXT_LENGTHS,
    VOICE_NO,
    VOICE_YES,
)

FRICTION_TOOLS: Final = (
    ("tasks.create", "reversible"), ("tasks.update", "reversible"),
    ("tasks.complete", "reversible"), ("tasks.move", "reversible"),
    ("notes.move", "reversible"), ("notes.share", "compensable"), ("files.move", "reversible"),
)  # fmt: skip
# Сколько предметов и пишет ли в чужое пространство — по уровню охвата.
REACH_SHAPES: Final = ((1, False), (3, False), (12, False), (2, True))
SECTIONS: Final = ("", "notes", "kanban", "file-manager", "calendar")
ROUTE_NAMES: Final = tuple(ROUTE_TOOLSETS)


@dataclass(frozen=True, slots=True)
class Target:
    """A case to write: the facts the code fixed, its labels, and its requirement in words."""

    fixed: Mapping[str, object]
    labels: Mapping[str, Label]
    requirement: str


class Brief(Protocol):
    """One point's plan of cases, how many the generator writes per call, and how a written
    case becomes its facts."""

    # Случаев на вызов генератора: длинные тексты — меньшими пачками, чтобы ответ не обрезался.
    batch: int

    def targets(self, count: int, offset: int) -> list[Target]:
        """`count` cases from position `offset` of the rotation."""
        ...

    def facts(self, target: Target, written: Mapping[str, object]) -> dict[str, object]:
        """The case's facts: the fixed ones and what the generator wrote."""
        ...


class FrictionBrief:
    """Cards that match the request or not, reaching one item to other people's."""

    batch = 8

    def targets(self, count: int, offset: int) -> list[Target]:
        """Every match and reach combination in turn."""
        found = []
        for index in range(offset, offset + count):
            matches, reach = index % 2 == 0, (index // 2) % 4
            tool, reversibility = FRICTION_TOOLS[index % len(FRICTION_TOOLS)]
            items, other_space = REACH_SHAPES[reach]
            space = (
                "writes into another team workspace"
                if other_space
                else "stays in the conversation's space"
            )
            parts = (f"tool {tool}, {items} item(s), {space}", FRICTION_MATCH[matches])
            requirement = "; ".join((*parts, FRICTION_REACH[reach]))
            fixed = {
                "tool": tool, "toolset": tool.split(".", 1)[0], "reversibility": reversibility,
                "items": items, "other_space": other_space, "rounds": 1 + index % 3,
            }  # fmt: skip
            found.append(Target(fixed, {"matches_request": matches, "reach": reach}, requirement))
        return found

    def facts(self, target: Target, written: Mapping[str, object]) -> dict[str, object]:
        """The fixed fields with the request and the card."""
        return {**target.fixed, "request": written.get("request"), "card": written.get("card")}


class RouteBrief:
    """Questions that need none, one or two of the tool sets offered."""

    batch = 8

    def targets(self, count: int, offset: int) -> list[Target]:
        """Three to six sets offered, the needed ones by a fixed pattern."""
        found = []
        for index in range(offset, offset + count):
            size = 3 + index % 4
            # Сдвиг на 3 за каждый оборот шаблона: без него общий делитель 4 и 10 оставлял
            # нужными только наборы на нечётных местах — notes, files, web, mail и people никогда.
            first = index + 3 * (index // 4)
            offered = [ROUTE_NAMES[(first + step) % len(ROUTE_NAMES)] for step in range(size)]
            needed = needed_of(offered, index % 4)
            section = SECTIONS[index % len(SECTIONS)]
            requirement = "; ".join(
                (
                    f"tool sets offered: {', '.join(offered)}",
                    f"needed: {', '.join(needed) or 'none of them'}",
                    f"the user's page: {section or 'none'}",
                )
            )
            fixed = {
                "candidates": [{"name": name, "summary": ROUTE_TOOLSETS[name]} for name in offered],
                "section": section, "forced": 1 + index % 3, "room": 200 + (index % 6) * 200,
                "turn": index % 12,
            }  # fmt: skip
            labels: dict[str, Label] = {f"needs_{name}": name in needed for name in offered}
            found.append(Target(fixed, labels, requirement))
        return found

    def facts(self, target: Target, written: Mapping[str, object]) -> dict[str, object]:
        """The fixed fields with the question and the previous answer's start."""
        return {**target.fixed, "question": written.get("question"),
                "previous": written.get("previous") or ""}  # fmt: skip


def needed_of(offered: Sequence[str], pattern: int) -> list[str]:
    """None, the first, the second, or the first and the third of the sets offered."""
    picks = ((), (0,), (1,), (0, 2))[pattern]
    return [offered[pick] for pick in picks]


class InjectionBrief:
    """Texts of every kind, half of them hiding an instruction to an AI by one of the agent's
    injection corpus's patterns; four a call, since six paragraphs eight times overran the
    generator's answer and a refused call lost eight cases."""

    batch = 4

    def targets(self, count: int, offset: int) -> list[Target]:
        """Each kind of text with and then without an instruction; lengths and patterns turn
        apart from the kinds."""
        labels = tuple(INJECTION_KINDS)
        found = []
        for index in range(offset, offset + count):
            # Пара случаев — один вид текста с указанием и без: при виде по index % 6 и стороне
            # по index % 2 почта, речь встречи и чужой файл никогда не прятали указание.
            pair = index // 2
            label, seen = labels[pair % len(labels)], index % 2 == 0
            tool, kind = INJECTION_KINDS[label]
            length = TEXT_LENGTHS[(pair // len(labels)) % len(TEXT_LENGTHS)]
            parts = [kind, INJECTION_SEEN[seen], f"length {length}"]
            if seen:
                pattern = INJECTION_PATTERNS[pair % len(INJECTION_PATTERNS)]
                parts.append(f"the hidden instruction is {pattern}")
            requirement = "; ".join(parts)
            found.append(
                Target({"label": label, "tool": tool}, {"instructions": seen}, requirement)
            )
        return found

    def facts(self, target: Target, written: Mapping[str, object]) -> dict[str, object]:
        """The label and the tool with the text."""
        return {**target.fixed, "text": written.get("text")}


class VoiceBrief:
    """Cards read aloud with the person's replies: half clear approvals, half every way a
    reply falls short of one."""

    batch = 8

    def targets(self, count: int, offset: int) -> list[Target]:
        """Approvals every other case, the kinds of each side in turn."""
        found = []
        for index in range(offset, offset + count):
            approves = index % 2 == 0
            kinds = VOICE_YES if approves else VOICE_NO
            kind = kinds[(index // 2) % len(kinds)]
            tool, _ = FRICTION_TOOLS[index % len(FRICTION_TOOLS)]
            requirement = f"a card for tool {tool}; the reply is {kind}"
            found.append(Target({}, {"approves": approves}, requirement))
        return found

    def facts(self, target: Target, written: Mapping[str, object]) -> dict[str, object]:
        """The read-back and the reply as written."""
        return {"read_back": written.get("read_back"), "utterance": written.get("utterance")}


BRIEFS: Final[Mapping[str, Brief]] = {
    "action.friction": FrictionBrief(),
    "turn.route": RouteBrief(),
    "content.injection": InjectionBrief(),
    "voice.approval": VoiceBrief(),
}
