"""What a slice asks core to send: one mail, by template, to one person (F6 plan §3.8)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final
from uuid import UUID

from shosai.core.i18n.locales import LOCALE_BY_CODE

# Адрес проверяется грубо, но без пробелов и переводов строк: заголовок не разорвать.
ADDRESS_CHAR: Final = r"[^\s@<>\"(),;:]"
ADDRESS: Final = re.compile(rf"{ADDRESS_CHAR}{{1,64}}@{ADDRESS_CHAR}{{1,190}}\.[A-Za-z]{{2,24}}")
CAMPAIGN_KEY: Final = re.compile(r"[a-z0-9_.:-]{1,64}")
TEMPLATE_KEY: Final = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")

type EmailParam = str | int | bool | None


class EmailKind(StrEnum):
    """What a mail is about: it picks the mailbox (F6-C11) and whether a person may leave it."""

    # Коды, сбросы, приветствие, чеки: не отписываются никогда.
    ACCOUNT = "account"
    NOTIFICATION = "notification"
    NEWSLETTER = "newsletter"


@dataclass(frozen=True, slots=True)
class OutgoingEmail:
    """One mail to one person: the template, its language and parameters.

    `secrets` hold what must never be logged — codes, reset links; they are encrypted in the
    row. `user_id` names the person whose unsubscriptions apply; a mail to an address alone
    (an invitation to someone without an account) has none, and a newsletter always has one.
    """

    recipient: str
    kind: EmailKind
    template: str
    locale: str
    params: Mapping[str, EmailParam] = field(default_factory=dict)
    secrets: Mapping[str, str] = field(default_factory=dict)
    user_id: UUID | None = None
    reply_to: str | None = None
    unsubscribe_url: str | None = None
    campaign_key: str | None = None

    def __post_init__(self) -> None:
        if not ADDRESS.fullmatch(self.recipient):
            message = "адрес получателя письма не похож на адрес почты"
            raise ValueError(message)
        if self.reply_to is not None and not ADDRESS.fullmatch(self.reply_to):
            message = "адрес для ответа не похож на адрес почты"
            raise ValueError(message)
        if not TEMPLATE_KEY.fullmatch(self.template) or len(self.template) > 64:
            message = "ключ шаблона — «срез.имя» в snake_case, до 64 символов"
            raise ValueError(message)
        if self.locale not in LOCALE_BY_CODE:
            message = "язык письма — один из 16 языков платформы"
            raise ValueError(message)
        if self.campaign_key is not None and not CAMPAIGN_KEY.fullmatch(self.campaign_key):
            message = "ключ рассылки — код до 64 символов"
            raise ValueError(message)
        if set(self.params) & set(self.secrets):
            message = "параметр письма не может быть и открытым, и секретным"
            raise ValueError(message)
        if self.kind is EmailKind.NEWSLETTER and self.user_id is None:
            message = "рассылку получает только человек с аккаунтом: от неё отписываются"
            raise ValueError(message)
