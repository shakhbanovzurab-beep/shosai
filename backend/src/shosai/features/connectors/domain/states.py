"""States of grants and connections, and the problems that only the person can fix.

A grant is `active`, `needs_reconnect` with a problem, or `revoking` while the provider's
revocation runs after its last app was disconnected. A connection shows its grant's state
unless it has a problem of its own — a missing scope is one app's, a refused refresh the
whole grant's. `needs_reconnect` holds exactly when there is a problem (plan §3.8), and the
same rule is a `CHECK` in the database.
"""

from dataclasses import dataclass
from enum import StrEnum


class GrantStatus(StrEnum):
    """Where a provider account's consent stands."""

    ACTIVE = "active"
    NEEDS_RECONNECT = "needs_reconnect"
    REVOKING = "revoking"


class ConnectionStatus(StrEnum):
    """Where an app stands for its person or workspace."""

    ACTIVE = "active"
    NEEDS_RECONNECT = "needs_reconnect"


class Problem(StrEnum):
    """Why a grant or a connection needs the person; each code is worded by the cabinet."""

    # Провайдер отказал в обновлении токена: грант отозван, истёк или токен пропал.
    REFRESH_REFUSED = "refresh_refused"
    # Свежий токен получил 401: доступ отозван у провайдера.
    GRANT_REVOKED = "grant_revoked"
    # Нет нужного приложению права: человек снял галочку или грант старый.
    SCOPE_MISSING = "scope_missing"
    # Рабочий тенант Microsoft требует одобрения администратора.
    ADMIN_CONSENT_REQUIRED = "admin_consent_required"
    # Яндекс: IMAP или токены OAuth выключены в настройках почты.
    IMAP_DISABLED = "imap_disabled"
    # Mail.ru: доступ сторонних программ только с подпиской Mail Space.
    PROVIDER_SUBSCRIPTION_REQUIRED = "provider_subscription_required"
    # Пароль приложения или ключ больше не принимается.
    CREDENTIALS_REJECTED = "credentials_rejected"


# Проблемы гранта целиком — все его приложения ждут человека.
GRANT_PROBLEMS = frozenset({
    Problem.REFRESH_REFUSED, Problem.GRANT_REVOKED, Problem.ADMIN_CONSENT_REQUIRED,
    Problem.IMAP_DISABLED, Problem.PROVIDER_SUBSCRIPTION_REQUIRED,
    Problem.CREDENTIALS_REJECTED,
})  # fmt: skip
# Проблемы одного приложения: у других приложений гранта всё работает.
CONNECTION_PROBLEMS = frozenset({Problem.SCOPE_MISSING})


class StateRuleError(ValueError):
    """A status and a problem that contradict each other."""


@dataclass(frozen=True, slots=True)
class GrantState:
    """A grant's status and its problem, consistent by construction."""

    status: GrantStatus
    problem: Problem | None = None

    def __post_init__(self) -> None:
        if (self.status is GrantStatus.NEEDS_RECONNECT) != (self.problem is not None):
            message = "грант ждёт человека тогда и только тогда, когда у него есть проблема"
            raise StateRuleError(message)
        if self.problem is not None and self.problem not in GRANT_PROBLEMS:
            message = f"проблема {self.problem} принадлежит приложению, не гранту"
            raise StateRuleError(message)

    @property
    def usable(self) -> bool:
        """Whether apps may call the provider with this grant."""
        return self.status is GrantStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class ConnectionState:
    """A connection's status and its problem, consistent by construction."""

    status: ConnectionStatus
    problem: Problem | None = None

    def __post_init__(self) -> None:
        if (self.status is ConnectionStatus.NEEDS_RECONNECT) != (self.problem is not None):
            message = "приложение ждёт человека тогда и только тогда, когда у него есть проблема"
            raise StateRuleError(message)


ACTIVE_GRANT = GrantState(GrantStatus.ACTIVE)
ACTIVE_CONNECTION = ConnectionState(ConnectionStatus.ACTIVE)


def grant_broken(problem: Problem) -> GrantState:
    """The state of a grant that lost its access for `problem`."""
    return GrantState(GrantStatus.NEEDS_RECONNECT, problem)


def connection_broken(problem: Problem) -> ConnectionState:
    """The state of one app that lacks what it needs."""
    if problem not in CONNECTION_PROBLEMS:
        message = f"проблема {problem} принадлежит гранту, не приложению"
        raise StateRuleError(message)
    return ConnectionState(ConnectionStatus.NEEDS_RECONNECT, problem)


def shown_state(grant: GrantState, own: ConnectionState) -> ConnectionState:
    """What a connection shows: the grant's problem first, then its own.

    A revoking grant has no live connections, so it is never shown; a caller that meets one
    has read a row the disconnect is about to delete, and the app reads as needing the person.
    """
    if grant.status is GrantStatus.REVOKING:
        return ConnectionState(ConnectionStatus.NEEDS_RECONNECT, Problem.GRANT_REVOKED)
    if grant.problem is not None:
        return ConnectionState(ConnectionStatus.NEEDS_RECONNECT, grant.problem)
    return own


def broken_transition(before: ConnectionState, after: ConnectionState) -> bool:
    """Whether a change of what a connection shows is news: it newly needs the person.

    `connectors.connection.broken` is emitted once per transition (CN-D11): a change from one
    problem to another, or a repeated failure, is not a new event.
    """
    return before.status is ConnectionStatus.ACTIVE and after.status is not before.status
