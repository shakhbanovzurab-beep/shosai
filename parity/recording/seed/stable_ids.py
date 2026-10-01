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
