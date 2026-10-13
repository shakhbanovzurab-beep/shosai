"""Shared model of the harness: compatibility classes, findings and the report.

A finding describes one deviation of v2 from the draft baseline. Its severity is
derived from two axes: how dangerous the change is for a client (`Impact`) and who
uses the endpoint (`CompatClass`).
"""

from dataclasses import dataclass, field, replace
from enum import StrEnum


class CompatClass(StrEnum):
    """Who uses an endpoint or a frame, and therefore whether it may change."""

    NATIVE = "native"  # выпущенный нативный клиент: менять нельзя (nfr-12)
    EXTERNAL = "external"  # внешние интеграции, ссылки в письмах, пробы: менять нельзя
    WEB = "web"  # только веб-фронтенд: меняется вместе с фронтендом v2
    UNUSED = "unused"  # потребитель не найден
    EXCLUDED = "excluded"  # вне контракта, причина записана в базе

    @property
    def must_stay_compatible(self) -> bool:
        """The endpoint must stay compatible without a client update."""
        return self in {CompatClass.NATIVE, CompatClass.EXTERNAL}


# Порядок от самого строгого класса к самому свободному: так классы идут в документах базы.
CLASS_STRENGTH: tuple[CompatClass, ...] = (
    CompatClass.NATIVE,
    CompatClass.EXTERNAL,
    CompatClass.WEB,
    CompatClass.UNUSED,
    CompatClass.EXCLUDED,
)


class Impact(StrEnum):
    """How dangerous a change is for a client written against the draft."""

    BREAKING = "breaking"  # клиент гарантированно сломается или потеряет данные
    RISKY = "risky"  # клиент может сломаться; нужна проверка человеком


class Severity(StrEnum):
    """Final severity of a finding in the report."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


def severity_for(impact: Impact, compat_class: CompatClass) -> Severity:
    """Severity = the change's impact x the consumer class."""
    if compat_class.must_stay_compatible:
        return Severity.ERROR if impact is Impact.BREAKING else Severity.WARNING
    if compat_class is CompatClass.WEB:
        return Severity.WARNING if impact is Impact.BREAKING else Severity.INFO
    return Severity.INFO


@dataclass(frozen=True, slots=True)
class Difference:
    """A difference found by a comparison, before it is tied to an endpoint and a class."""

    rule: str
    impact: Impact
    pointer: str
    message: str


@dataclass(frozen=True, slots=True)
class Finding:
    """A difference tied to an endpoint or a frame, with its final severity."""

    rule: str
    subject: str
    pointer: str
    message: str
    impact: Impact
    compat_class: CompatClass
    slice_id: str
    severity: Severity
    accepted_reason: str = ""

    @property
    def finding_id(self) -> str:
        """Stable identifier for the list of deliberately accepted deviations."""
        suffix = f" {self.pointer}" if self.pointer else ""
        return f"{self.rule} {self.subject}{suffix}"

    def accept(self, reason: str) -> Finding:
        """Mark the finding as accepted: it stays in the report but does not fail the check."""
        return replace(self, accepted_reason=reason, severity=Severity.INFO)


def locate(
    difference: Difference, subject: str, compat_class: CompatClass, slice_id: str
) -> Finding:
    """Tie a difference to an endpoint and derive its severity."""
    return Finding(
        rule=difference.rule,
        subject=subject,
        pointer=difference.pointer,
        message=difference.message,
        impact=difference.impact,
        compat_class=compat_class,
        slice_id=slice_id,
        severity=severity_for(difference.impact, compat_class),
    )


@dataclass(frozen=True, slots=True)
class Coverage:
    """How many baseline items the check covered, so an empty report does not look like a win."""

    operations: int = 0
    routes: int = 0
    websocket_endpoints: int = 0
    websocket_frames: int = 0
    untyped_responses: int = 0


@dataclass(frozen=True, slots=True)
class Report:
    """Result of checking a v2 candidate against the draft baseline."""

    findings: tuple[Finding, ...]
    coverage: Coverage = field(default_factory=Coverage)
    unused_acceptances: tuple[str, ...] = ()
    # Эндпоинты черновика в охвате, которых v2 ещё не обслуживает (только при served_only).
    unserved: tuple[str, ...] = ()

    def count(self, severity: Severity) -> int:
        """Number of findings with the given severity."""
        return sum(1 for finding in self.findings if finding.severity is severity)

    @property
    def is_compatible(self) -> bool:
        """Compatible when no unaccepted error remains.

        Unused acceptances are only shown: when one slice is checked, the acceptances of
        other slices legitimately match nothing.
        """
        return self.count(Severity.ERROR) == 0
