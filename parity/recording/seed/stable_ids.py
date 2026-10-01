"""Стабильные идентификаторы и токены засева: общий файл с визитами записи (ids.json)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

_IDS: dict[str, Any] = json.loads((Path(__file__).with_name("ids.json")).read_text(encoding="utf-8"))

#: Встречи персоны «руководитель» по ключу засева → UUID строкой.
MEETINGS: dict[str, str] = dict(_IDS["meetings"])
#: Реплика «Бюджета», на которую ссылаются задача и влияние.
BUDGET_SEGMENT = uuid.UUID(_IDS["budgetSegment"])
#: Документ базы знаний, который визит подсвечивает по ссылке `?doc=`.
KNOWLEDGE_DOCUMENT = uuid.UUID(_IDS["knowledgeDocument"])
#: Токены публичных ссылок на итог встречи.
SHARES: dict[str, str] = dict(_IDS["shares"])
SHARE_PASSWORD: str = _IDS["sharePassword"]
ROOM_INVITE: str = _IDS["roomInvite"]
STREAM_INVITE: str = _IDS["streamInvite"]
ICAL_TOKEN: str = _IDS["icalToken"]
#: Дела «руководителя»: клиент Acme, внутреннее «Северный ветер» и архивное.
HUBS: dict[str, uuid.UUID] = {key: uuid.UUID(value) for key, value in _IDS["hubs"].items()}
#: Промпты, которые визиты открывают в редакторе.
PROMPTS: dict[str, uuid.UUID] = {key: uuid.UUID(value) for key, value in _IDS["prompts"].items()}
#: Открытый токен сервера MCP: черновик хранит хеш и показывает маску по нему.
MCP_TOKEN: str = _IDS["mcp"]["token"]
#: Клиент OAuth, которого экран согласия находит без сети.
MCP_CLIENT_ID: str = _IDS["mcp"]["clientId"]
MCP_REDIRECT_URI: str = _IDS["mcp"]["redirectUri"]
MCP_SCOPES: tuple[str, ...] = tuple(_IDS["mcp"]["scopes"])
#: Комнаты «руководителя»: видеовстреча с Acme и сцена трансляции.
ROOMS: dict[str, uuid.UUID] = {key: uuid.UUID(value) for key, value in _IDS["rooms"].items()}
#: Трансляции «руководителя»: студия открывается по id.
STREAMS: dict[str, uuid.UUID] = {key: uuid.UUID(value) for key, value in _IDS["streams"].items()}
#: Приглашения в комнаты сверх календарных: со сквозным шифрованием и закрытая.
ROOM_INVITES: dict[str, str] = dict(_IDS["roomInvites"])
#: Токены публичных ссылок на файлы и папки.
FILE_SHARES: dict[str, str] = dict(_IDS["fileShares"])
#: Приглашения на трансляции сверх календарной: в эфире, завершённая, для своих.
STREAM_INVITES: dict[str, str] = dict(_IDS["streamInvites"])
#: Токены заявок на вход в эфир: зритель хранит свой в sessionStorage.
KNOCKS: dict[str, str] = dict(_IDS["knocks"])
#: Доски трекера «руководителя» по коду проекта.
BOARDS: dict[str, uuid.UUID] = {key: uuid.UUID(value) for key, value in _IDS["boards"].items()}
