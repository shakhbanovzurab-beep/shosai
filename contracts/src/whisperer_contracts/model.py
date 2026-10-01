"""Общая модель харнесса: классы совместимости, находки и отчёт.

Находка («finding») описывает одно расхождение v2 с базой черновика. Её
серьёзность выводится из двух осей: насколько изменение опасно для клиента
(`Impact`) и кто этим адресом пользуется (`CompatClass`).
"""

from dataclasses import dataclass, field, replace
from enum import StrEnum


class CompatClass(StrEnum):
    """Кто пользуется адресом или кадром — отсюда, можно ли его менять."""

    NATIVE = "native"  # выпущенный нативный клиент: менять нельзя (nfr-12)
    EXTERNAL = "external"  # внешние интеграции, ссылки в письмах, пробы: менять нельзя
    WEB = "web"  # только веб-фронтенд: меняется вместе с фронтендом v2
    UNUSED = "unused"  # потребитель не найден
    EXCLUDED = "excluded"  # вне контракта, причина записана в базе

    @property
    def must_stay_compatible(self) -> bool:
        """Адрес обязан остаться совместимым без обновления клиента."""
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
    """Насколько изменение опасно для клиента, написанного под черновик."""

    BREAKING = "breaking"  # клиент гарантированно сломается или потеряет данные
    RISKY = "risky"  # клиент может сломаться; нужна проверка человеком


class Severity(StrEnum):
    """Итоговая серьёзность находки в отчёте."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


def severity_for(impact: Impact, compat_class: CompatClass) -> Severity:
    """Серьёзность = опасность изменения x класс потребителя."""
    if compat_class.must_stay_compatible:
        return Severity.ERROR if impact is Impact.BREAKING else Severity.WARNING
    if compat_class is CompatClass.WEB:
        return Severity.WARNING if impact is Impact.BREAKING else Severity.INFO
    return Severity.INFO


@dataclass(frozen=True, slots=True)
class Difference:
    """Расхождение, найденное сравнением, до привязки к адресу и классу."""

    rule: str
    impact: Impact
    pointer: str
    message: str


@dataclass(frozen=True, slots=True)
class Finding:
    """Расхождение, привязанное к адресу или кадру, с итоговой серьёзностью."""

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
        """Стабильный идентификатор для списка осознанно принятых расхождений."""
        suffix = f" {self.pointer}" if self.pointer else ""
        return f"{self.rule} {self.subject}{suffix}"

    def accept(self, reason: str) -> Finding:
        """Помечает находку принятой: она остаётся в отчёте, но не валит проверку."""
        return replace(self, accepted_reason=reason, severity=Severity.INFO)


def locate(
    difference: Difference, subject: str, compat_class: CompatClass, slice_id: str
) -> Finding:
    """Привязывает расхождение к адресу и выводит его серьёзность."""
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
    """Сколько элементов базы попало в проверку — чтобы пустой отчёт не выглядел победой."""

    operations: int = 0
    routes: int = 0
    websocket_endpoints: int = 0
    websocket_frames: int = 0
    untyped_responses: int = 0


@dataclass(frozen=True, slots=True)
class Report:
    """Результат проверки кандидата v2 против базы черновика."""

    findings: tuple[Finding, ...]
    coverage: Coverage = field(default_factory=Coverage)
    unused_acceptances: tuple[str, ...] = ()

    def count(self, severity: Severity) -> int:
        """Число находок данной серьёзности."""
        return sum(1 for finding in self.findings if finding.severity is severity)

    @property
    def is_compatible(self) -> bool:
        """Совместим, если не осталось ни одной непринятой ошибки.

        Неиспользованные принятия только показываются: при проверке одного
        среза принятия других срезов законно ни с чем не совпадают.
        """
        return self.count(Severity.ERROR) == 0
