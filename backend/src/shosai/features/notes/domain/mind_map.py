"""The meeting's mind map, projected from its findings without a model call (plan §1.2).

The root is the meeting's title; its children are the topics the findings name, in the
order they first came up; each topic's children are its findings in the meeting's order.
A topic shows two to five findings; one named by a single finding stays out of the map
(the finding is still in the write-up). At most six topics, the largest; so whenever three
topics have two findings each, the map has three to six topics of two to five children.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from shosai.features.notes.domain.findings import Finding

TOPICS_MAX: Final = 6
CHILDREN_MIN: Final = 2
CHILDREN_MAX: Final = 5
LABEL_MAX: Final = 120


@dataclass(frozen=True, slots=True)
class MapNode:
    """A node of the map: its label and its children."""

    label: str
    children: tuple[MapNode, ...] = field(default=())


def project_map(title: str, findings: Sequence[Finding]) -> MapNode:
    """The map of a meeting titled `title` from its findings, in the meeting's order."""
    groups: dict[str, tuple[str, list[Finding]]] = {}
    for finding in sorted(findings, key=lambda f: f.evidence.start_ms):
        if finding.topic is None:
            continue
        key = finding.topic.casefold()
        groups.setdefault(key, (finding.topic, []))[1].append(finding)
    eligible = [group for group in groups.values() if len(group[1]) >= CHILDREN_MIN]
    # Крупнейшие темы, при равенстве — раньше прозвучавшие; на карте — в порядке встречи.
    largest = sorted(range(len(eligible)), key=lambda index: -len(eligible[index][1]))
    kept = [eligible[index] for index in sorted(largest[:TOPICS_MAX])]
    topics = tuple(
        MapNode(
            label=label[:LABEL_MAX],
            children=tuple(MapNode(f.text[:LABEL_MAX]) for f in members[:CHILDREN_MAX]),
        )
        for label, members in kept
    )
    return MapNode(label=title[:LABEL_MAX], children=topics)
