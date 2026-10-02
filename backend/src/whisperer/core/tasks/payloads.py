"""Task payloads: one Pydantic model per task (target architecture §12, §14 rule 9).

A payload is frozen and ignores fields it does not know: consumers are deployed before
producers, so a new field is optional for the consumer, and a consumer rolled back to an
older image still accepts what a newer producer sent. A home-scoped task names its home in
the payload; the handler opens its transactions there (§4.1 rule 3).

A secret — a password-reset link, a one-time code — is a `TaskSecret` field: it travels
in the stream as plain text, so the worker can use it, and is masked wherever a payload is
kept for diagnosis, such as the dead letter.
"""

from collections.abc import Mapping
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PlainSerializer, SecretStr, SerializationInfo

from whisperer.core.kernel.homes import Home
from whisperer.core.kernel.tenancy import TenancyScope
from whisperer.core.observability.log_context import LogFields
from whisperer.core.observability.redaction import REDACTED

# Флаг контекста сериализации: при нём секреты задачи заменяются маской (core/tasks/dead_letter.py).
MASK_SECRETS: Final = "mask_secrets"


def serialize_task_secret(value: SecretStr, info: SerializationInfo) -> str:
    """The secret itself for the stream; the mask when the payload is kept for diagnosis."""
    context = info.context
    if isinstance(context, Mapping) and context.get(MASK_SECRETS):
        return REDACTED
    return value.get_secret_value()


# Обычный псевдоним, а не `type`: так pydantic видит сериализатор в метаданных поля.
TaskSecret = Annotated[
    SecretStr, PlainSerializer(serialize_task_secret, return_type=str, when_used="json")
]


class TaskPayload(BaseModel):
    """The payload of one task: ids, codes and numbers a handler needs to do its work."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    def log_fields(self) -> LogFields:
        """The ids this payload adds to the log lines of its run."""
        return {}


class HomeTaskPayload(TaskPayload):
    """The payload of a task that acts in one data home, for an account or a company."""

    home: Home
    user_id: UUID | None = None
    org_id: UUID | None = None

    def scope(self) -> TenancyScope:
        """The tenancy scope the handler opens its transactions in."""
        return TenancyScope(self.home, self.user_id, self.org_id)

    def log_fields(self) -> LogFields:
        """The home and, when known, the account and the company."""
        fields: LogFields = {"home": self.home}
        if self.user_id is not None:
            fields["user_id"] = self.user_id
        if self.org_id is not None:
            fields["org_id"] = self.org_id
        return fields
