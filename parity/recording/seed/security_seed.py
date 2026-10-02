"""Security in the admin: account sharing, the model error log and the abuse queue.

The draft detects sharing from successful sign-ins from four or more IPs within a day.
Its personas (`sharer`, `sharer2`) never sign in during visits: the recorder's sign-in
would add one more IP. The addresses come from the documentation ranges (RFC 5737).

The model proxy writes the error log; three entries are within the last hour. The API
clock stands at the parity clock, so "within an hour" does not depend on when the visit
is recorded.

The abuse queue: flagged (`abuser`), moved to the cheap route (`cheap`) and flagged
while whitelisted (`trusted`; the hard signal fires for it too). The scores differ: the
queue is sorted by them, and the database would return ties in any order.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from meetassist.models.abuse_event import AbuseEvent
from meetassist.models.abuse_state import AbuseState
from meetassist.models.error_log import ErrorLog
from meetassist.models.login_event import LoginEvent
from meetassist.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

_SAFARI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
_ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"

#: Входы: персона, IP, браузер, минут назад, успешен.
_LOGINS = (
    ("sharer", "203.0.113.14", _SAFARI, 35, True),
    ("sharer", "198.51.100.23", _CHROME, 170, True),
    ("sharer", "192.0.2.41", _ANDROID, 330, True),
    ("sharer", "203.0.113.77", _CHROME, 520, True),
    ("sharer", "198.51.100.90", _SAFARI, 760, True),
    ("sharer", "192.0.2.118", _ANDROID, 1140, True),
    ("sharer", "192.0.2.118", _ANDROID, 1145, False),
    ("sharer2", "203.0.113.200", _CHROME, 95, True),
    ("sharer2", "198.51.100.7", _SAFARI, 410, True),
    ("sharer2", "192.0.2.66", _CHROME, 690, True),
    ("sharer2", "203.0.113.151", _ANDROID, 980, True),
)

#: Журнал ошибок: минут назад, уровень, код, источник, сообщение, модель.
_ERRORS = (
    (1, "error", None, "llm:openrouter", "rate_limited", "anthropic/claude-sonnet-5.5"),
    (3, "error", None, "llm:openrouter", "upstream_error_502", "openai/gpt-5.1"),
    (5, "error", None, "translate:openrouter", "upstream_stalled", "google/gemini-3-flash"),
    (130, "warn", 429, "llm:openrouter", "rate_limited: retry after 20s", "anthropic/claude-sonnet-5.5"),
    (310, "error", None, "llm:openrouter", "model_unavailable", "deepseek/deepseek-v4-flash"),
    (640, "error", None, "translate:openrouter", "upstream_error", "google/gemini-3-flash"),
    (1190, "error", None, "llm:openrouter", "insufficient_balance", "openai/gpt-5.1"),
)

_FEATURES = {"burn": 0.92, "interval_var": 0.08, "concurrency": 3, "dup_ratio": 0.61, "gibberish_ratio": 0.04,
             "vision_share": 0.0, "sustained": True, "context_len": 48_000, "automation": 0.87}

#: Очередь abuse: персона, состояние, оценка, белый список, уведомлён (часов назад),
#: события (часов назад, из, в, оценка, действие).
_QUEUE = (
    ("abuser", "flagged", 0.9312, False, 3, (
        (48, "normal", "observe", 0.5410, "observe"),
        (24, "observe", "route_cheap", 0.7920, "route_cheap"),
        (3, "route_cheap", "flagged", 0.9312, "flagged"),
        (2.99, "route_cheap", "flagged", 0.9312, "notify"),
    )),
    ("cheap", "route_cheap", 0.7845, False, None, (
        (30, "normal", "observe", 0.5630, "observe"),
        (6, "observe", "route_cheap", 0.7845, "route_cheap"),
    )),
    ("trusted", "flagged", 0.6120, True, 9, (
        (10, "normal", "flagged", 0.6120, "flagged"),
        (8.99, "normal", "flagged", 0.6120, "notify"),
    )),
)


async def seed_security(db: AsyncSession, accounts: dict[str, User], clock: datetime) -> None:
    """Seed sign-ins from different IPs, the error log and the abuse queue with its history."""
    for key, ip, agent, minutes, success in _LOGINS:
        db.add(LoginEvent(user_id=accounts[key].id, ip=ip, user_agent=agent, outcome="success" if success else "failed",
                          created_at=clock - timedelta(minutes=minutes)))
    for minutes, level, code, source, message, model in _ERRORS:
        db.add(ErrorLog(level=level, code=code, source=source, message=message,
                        context={"model": model, "role": "chat"}, created_at=clock - timedelta(minutes=minutes)))
    for key, state, score, whitelisted, notified, events in _QUEUE:
        user = accounts[key]
        db.add(AbuseState(user_id=user.id, state=state, score=score, whitelisted=whitelisted, confirm_windows=2,
                          updated_at=clock - timedelta(hours=events[-1][0]),
                          notified_at=None if notified is None else clock - timedelta(hours=notified)))
        for hours, before, after, value, action in events:
            db.add(AbuseEvent(user_id=user.id, at=clock - timedelta(hours=hours), from_state=before, to_state=after,
                              score=value, features=_FEATURES if action != "notify" else None, action=action,
                              actor="system"))
    await db.flush()
