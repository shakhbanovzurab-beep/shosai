"""What a request learns about its caller on the way in: the home and the person (§16.2, §16.7).

The request boundary puts one empty `RequestFacts` into the ASGI scope's state before the
app runs; the dependency that authenticates the caller fills it. The boundary then reads it
for the HTTP metric's `home` label, and every log line of the request written after the
caller is known — the access line included — carries the ids (`late_log_fields`). Only ids
live here — never a name or an address.
"""

from dataclasses import dataclass
from uuid import UUID

from opentelemetry import trace
from starlette.requests import Request
from starlette.types import Scope

from shosai.core.kernel.homes import Home
from shosai.core.observability.log_context import LogFields

STATE = "state"
FACTS_KEY = "shosai.request_facts"
# Тот же атрибут дома, что у спанов запросов к базе (core/db/tracing.py); user.id — по семантическим
# соглашениям OpenTelemetry. Идентификаторы в трейсах допустимы (§16.7), имена и адреса — нет.
HOME_SPAN_ATTRIBUTE = "shosai.home"
USER_SPAN_ATTRIBUTE = "user.id"


@dataclass(slots=True)
class RequestFacts:
    """The caller of one request, once known; empty for anonymous requests."""

    home: Home | None = None
    user_id: UUID | None = None

    def log_fields(self) -> LogFields:
        """The known ids as log fields."""
        fields = LogFields()
        if self.home is not None:
            fields["home"] = self.home
        if self.user_id is not None:
            fields["user_id"] = self.user_id
        return fields


def attach_facts(scope: Scope) -> RequestFacts:
    """A fresh record in the scope's state; the boundary calls it once per request."""
    facts = RequestFacts()
    scope.setdefault(STATE, {})[FACTS_KEY] = facts
    return facts


def note_caller(request: Request, home: Home, user_id: UUID) -> None:
    """Record the authenticated caller for the boundary, the request's span and its log lines.

    Outside the boundary (a test calling a dependency directly) only the span is marked.
    """
    facts = request.scope.get(STATE, {}).get(FACTS_KEY)
    if isinstance(facts, RequestFacts):
        facts.home = home
        facts.user_id = user_id
    span = trace.get_current_span()
    span.set_attribute(HOME_SPAN_ATTRIBUTE, home.value)
    span.set_attribute(USER_SPAN_ATTRIBUTE, str(user_id))
