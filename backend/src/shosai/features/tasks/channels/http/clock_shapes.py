"""A task's time fields and its chat source as the contract's shapes (`domain/time-contract.ts`,
`domain/tasks-contract.ts`; §3.9, §3.10)."""

from datetime import datetime

from pydantic import BaseModel

from shosai.features.tasks.channels.http.card_models import (
    StopwatchOut,
    TimerOut,
    TimeTrackingOut,
)
from shosai.features.tasks.channels.http.detail_models import ChatMessageOut, ChatSourceOut
from shosai.features.tasks.domain.chat_source import ChatOrigin
from shosai.features.tasks.domain.clocks import TaskClocks


class ClocksReply(BaseModel):
    """What a clock's action answers: the three time fields and the server's moment."""

    stopwatch: StopwatchOut | None
    timer: TimerOut | None
    time_tracking: TimeTrackingOut | None
    server_now: datetime


def clocks_out(clocks: TaskClocks) -> dict[str, object]:
    """The three time fields of a card, each null while unused, as the plain values the
    card's model validates in one pass."""
    watch, timer, tracking = clocks.stopwatch, clocks.timer, clocks.time_tracking
    return {
        "stopwatch": None
        if watch is None
        else {
            "running_since": watch.running_since,
            "total_ms": watch.total_ms,
            "by_column": watch.by_column,
        },
        "timer": None
        if timer is None
        else {
            "length_ms": timer.length_ms,
            "ends_at": timer.ends_at,
            "paused_left_ms": timer.paused_left_ms,
        },
        "time_tracking": None
        if tracking is None
        else {"plan_minutes": tracking.plan_minutes, "fact_minutes": tracking.fact_minutes},
    }


def clocks_reply(clocks: TaskClocks, server_now: datetime) -> ClocksReply:
    """A clock's action's answer."""
    return ClocksReply.model_validate({**clocks_out(clocks), "server_now": server_now})


def chat_source_out(origin: ChatOrigin | None) -> ChatSourceOut | None:
    """The chat and the message a task was made from."""
    if origin is None:
        return None
    return ChatSourceOut(
        connection_id=origin.connection_id,
        messenger=origin.messenger,
        chat_title=origin.chat_title,
        message=ChatMessageOut(url=origin.message_url, sent_at=origin.message_at),
    )
