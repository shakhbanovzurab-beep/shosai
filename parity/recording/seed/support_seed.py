"""Support tickets and broadcasts.

The tickets belong to `max` (three: resolved, in progress with an unread reply, and
open, where the user adds details while waiting), and one each to `free` (resolved) and
`pro` (in progress). The support agent is `admin`. The ticket number comes from a
database sequence, so the tickets are inserted one by one in date order.

The read markers are set explicitly: `max` has one unread reply, and `admin` has unread
messages in two tickets. Opening a ticket writes the marker itself, so visits open only
the tickets with no new messages.

Attachments would live in S3; without it the draft returns them without a link, as a
badge. Broadcasts: the emails are sent, the Telegram channel one is queued (the draft
never sends it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from meetassist.models import Broadcast, Ticket, TicketAttachment, TicketMessage
from meetassist.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


def _at(month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


@dataclass(frozen=True)
class _Message:
    staff: bool
    at: datetime
    body: str
    #: Вложение: имя, тип, размер.
    attachment: tuple[str, str, int] | None = None


@dataclass(frozen=True)
class _Ticket:
    owner: str
    subject: str
    status: str
    user_read: datetime | None
    admin_read: datetime | None
    messages: tuple[_Message, ...] = field(default_factory=tuple)


#: В каждом треде от 5 до 20 сообщений: черновик пишет «N сообщений» без
#: склонения (находка шага 7), и только такие числа он показывает верно.
_TICKETS = (
    _Ticket("free", "Как поменять язык интерфейса?", "resolved", _at(6, 27, 11, 41), _at(6, 27, 11, 45), (
        _Message(False, _at(6, 27, 10, 30), "Здравствуйте! Интерфейс открылся на английском, а нужен русский. Где это поменять?"),
        _Message(True, _at(6, 27, 11, 15), "Добрый день! Язык меняется в **Кабинет → Общие → Язык интерфейса**."),
        _Message(False, _at(6, 27, 11, 22), "Открыла кабинет, но такого пункта не вижу."),
        _Message(True, _at(6, 27, 11, 31), "Он внизу вкладки «Общие», под темой оформления. Выбор сохранится для всех ваших устройств."),
        _Message(False, _at(6, 27, 11, 40), "Нашла, спасибо!"),
    )),
    _Ticket("max", "Как скачать стенограмму встречи в Word?", "resolved", _at(7, 5, 16, 0), _at(7, 5, 15, 55), (
        _Message(False, _at(7, 5, 14, 20), "Нужно отправить стенограмму клиенту в формате Word. Есть такая выгрузка?"),
        _Message(True, _at(7, 5, 15, 2), "Да: откройте встречу, меню **⋯ → Скачать → DOCX**. В файл попадут стенограмма и AI-заметки."),
        _Message(False, _at(7, 5, 15, 20), "А можно без AI-заметок, только текст разговора?"),
        _Message(True, _at(7, 5, 15, 26), "Можно: в окне скачивания снимите галочку «AI-заметки»."),
        _Message(False, _at(7, 5, 15, 40), "Получилось, спасибо!"),
        _Message(True, _at(7, 5, 15, 55), "Рады помочь! Закрываем обращение."),
    )),
    _Ticket("max", "Не подключается Google Календарь", "open", _at(7, 16, 9, 20), None, (
        _Message(False, _at(7, 13, 16, 20), "При подключении календаря Google показывает ошибку доступа. Скриншот приложила.",
                 ("kalendar.png", "image/png", 186_940)),
        _Message(False, _at(7, 14, 9, 2), "Пробовала в другом браузере — то же самое."),
        _Message(False, _at(7, 15, 12, 30), "Ошибка «доступ запрещён» появляется сразу после выбора аккаунта."),
        _Message(False, _at(7, 16, 9, 12), "Есть новости?"),
        _Message(False, _at(7, 16, 9, 20), "Нашла в справке про права календаря — все галочки стоят."),
    )),
    _Ticket("max", "Запись обрывается на длинных встречах", "in_progress", _at(7, 15, 8, 11), _at(7, 16, 10, 5), (
        _Message(False, _at(7, 14, 7, 40), "Запись останавливается примерно через 40 минут, если встреча длинная. "
                                           "Прикладываю скриншот ошибки.",
                 ("oshibka-zapisi.png", "image/png", 248_312)),
        _Message(True, _at(7, 14, 9, 5), "Спасибо! Подскажите версию приложения и пришлите журнал записи — "
                                         "он в **Настройки → Диагностика**."),
        _Message(False, _at(7, 14, 9, 31), "Версия 1.4.5, macOS 14.5. Журнал во вложении.",
                 ("log-zapisi.txt", "text/plain", 12_874)),
        _Message(True, _at(7, 14, 9, 50), "Спасибо, передали разработчикам."),
        _Message(False, _at(7, 15, 8, 10), "Сегодня утром повторилось на планёрке."),
        _Message(True, _at(7, 16, 10, 5), "Нашли причину: запись прерывается при смене аудиоустройства. "
                                          "Исправление выйдет в 1.4.6, а пока отключите автопереключение микрофона."),
    )),
    _Ticket("pro", "Добавьте горячую клавишу для паузы записи", "in_progress", _at(7, 17, 8, 5), _at(7, 16, 14, 10), (
        _Message(False, _at(7, 15, 8, 5), "Было бы удобно ставить запись на паузу сочетанием клавиш, не переключаясь в окно."),
        _Message(True, _at(7, 15, 10, 30), "Хорошая идея! Какое сочетание было бы удобно?"),
        _Message(False, _at(7, 15, 11, 0), "Например, ⌘⇧P — его не занимают ни Zoom, ни Teams."),
        _Message(True, _at(7, 16, 14, 10), "Запланировали на версию 1.5. Напишем, когда выйдет."),
        _Message(False, _at(7, 17, 8, 5), "Отлично, ждём!"),
    )),
)

#: Рассылки: создана, канал, аудитория, тема, текст, статус, получателей, отправлено, отправлена.
_BROADCASTS = (
    (_at(7, 16, 8, 30), "telegram", "all", "Whisperer теперь в Telegram",
     "Подписывайтесь на канал: новости, советы и ранний доступ к новым функциям.", "queued", 11, 0, None),
    (_at(7, 12, 10, 0), "email", "all", "Whisperer 1.4.5: стабильная запись и новые горячие клавиши",
     "В версии 1.4.5 — стабильная запись длинных встреч и новые горячие клавиши.", "sent", 11, 11, _at(7, 12, 10, 0)),
    (_at(7, 10, 9, 0), "email", "paid", "Новое в Whisperer: календарь активности",
     "На странице «Активность» появился календарь: каждая встреча закрашивает свой день.", "sent", 5, 5, _at(7, 10, 9, 0)),
    (_at(6, 30, 14, 0), "email", "user", "Ответ на ваше обращение",
     "Мы ответили на ваше обращение в поддержку — откройте его в кабинете.", "sent", 1, 1, _at(6, 30, 14, 0)),
)


async def seed_support(db: AsyncSession, accounts: dict[str, User]) -> None:
    """Seed tickets with their messages and attachments, and the broadcast history."""
    staff = accounts["admin"]
    for spec in sorted(_TICKETS, key=lambda item: item.messages[0].at):
        owner = accounts[spec.owner]
        ticket = Ticket(user_id=owner.id, subject=spec.subject, status=spec.status, created_at=spec.messages[0].at,
                        user_last_read_at=spec.user_read, admin_last_read_at=spec.admin_read)
        db.add(ticket)
        await db.flush()
        for message in spec.messages:
            row = TicketMessage(ticket_id=ticket.id, author_user_id=staff.id if message.staff else owner.id,
                                body=message.body, created_at=message.at)
            db.add(row)
            await db.flush()
            if message.attachment is not None:
                name, mime, size = message.attachment
                db.add(TicketAttachment(message_id=row.id, filename=name, mime=mime, size=size,
                                        s3_key=f"tickets/{ticket.id}/{row.id}/{name}", created_at=message.at))
    for created, channel, audience, subject, body, status, recipients, sent, sent_at in _BROADCASTS:
        db.add(Broadcast(channel=channel, audience=audience, subject=subject, body=body, status=status,
                         recipients_count=recipients, sent_count=sent, sent_at=sent_at,
                         created_by_user_id=staff.id, created_at=created))
    await db.flush()
