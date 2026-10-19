"""From the model's findings to the meeting's: lines to offsets, labels to speakers, merges.

A finding cites the first and last line that prove it; both must be lines of the window
the model read, and their span becomes the evidence — a line number the model invented
drops the finding. An owner written as a speaker's label (`S2`) is that speaker; any other
owner is a name as said. Findings of overlapping windows that repeat one another exactly —
same kind, same span, same words — are kept once before the merging pass.
"""

import re
from collections.abc import Iterator, Sequence
from typing import Final

from shosai.features.meetings.domain.findings import Finding, FindingKind, RawFinding
from shosai.features.meetings.domain.transcript_text import SpokenLine, span
from shosai.features.meetings.infrastructure.prompts import (
    FINDINGS_HEADER,
    NO_FINDINGS,
    FoundItem,
)

SPEAKER_LABEL: Final = re.compile(r"\s*S(\d{1,2})\s*")


def owner_of(raw: str | None) -> tuple[int | None, str | None]:
    """A speaker's index for a label such as `S2`, else the name as said."""
    if raw is None or not raw.strip():
        return None, None
    label = SPEAKER_LABEL.fullmatch(raw)
    if label is not None and int(label.group(1)) >= 1:
        return int(label.group(1)) - 1, None
    return None, raw


def raw_findings(items: Sequence[FoundItem], window: Sequence[SpokenLine]) -> Iterator[RawFinding]:
    """The window's findings whose kind is known and whose lines are the window's."""
    for item in items:
        try:
            kind = FindingKind(item.kind.strip().lower())
        except ValueError:
            continue
        offsets = span(window, item.first_line, item.last_line)
        if offsets is None:
            continue
        speaker, name = owner_of(item.owner)
        yield RawFinding(
            kind=kind,
            text=item.text,
            start_ms=offsets[0],
            end_ms=offsets[1],
            quote=item.quote,
            topic=item.topic,
            owner_speaker=speaker,
            owner_name=name,
            due_on=item.due,
        )


def without_repeats(findings: Sequence[Finding]) -> list[Finding]:
    """The findings in the meeting's order, an exact repeat of an earlier one left out."""
    seen: set[tuple[FindingKind, int, int, str]] = set()
    kept: list[Finding] = []
    for finding in sorted(findings, key=lambda f: (f.evidence.start_ms, f.evidence.end_ms)):
        evidence = finding.evidence
        identity = (finding.kind, evidence.start_ms, evidence.end_ms, finding.text.casefold())
        if identity not in seen:
            seen.add(identity)
            kept.append(finding)
    return kept


def kept_by_merge(findings: Sequence[Finding], numbers: Sequence[int]) -> list[Finding]:
    """The findings the merge kept by their numbers from 1; all of them if it kept none."""
    chosen = sorted({n for n in numbers if 1 <= n <= len(findings)})
    return [findings[n - 1] for n in chosen] if chosen else list(findings)


def listed(findings: Sequence[Finding]) -> str:
    """The findings as a numbered list for a model: kind and statement."""
    if not findings:
        return f"{FINDINGS_HEADER}\n{NO_FINDINGS}"
    rows = (f"{n}. [{f.kind.value}] {f.text}" for n, f in enumerate(findings, 1))
    return "\n".join((FINDINGS_HEADER, *rows))
