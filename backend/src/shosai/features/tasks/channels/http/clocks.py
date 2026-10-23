"""A task's stopwatch and timer (`/v1/tasks/{id}/stopwatch/*`, `/v1/tasks/{id}/timer*`;
tasks plan §3.9, ADR 0061).

Every action answers the task's three time fields with the server's moment. Errors use the
platform's envelope with the codes the cabinet words: `task_not_found`, `timer_not_set`,
`jira_unsupported`, `validation_error`.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field

from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.tasks.application.clocks import Clocks, ClocksView
from shosai.features.tasks.channels.http.clock_shapes import ClocksReply, clocks_reply
from shosai.features.tasks.channels.http.strict import Strict
from shosai.features.tasks.domain.clocks import TIMER_MAX_MS, TIMER_MIN_MS


class TimerBody(Strict):
    """A timer's length: a minute to a year."""

    length_ms: int = Field(ge=TIMER_MIN_MS, le=TIMER_MAX_MS)


def reply_of(view: ClocksView) -> ClocksReply:
    """The answer of an action."""
    return clocks_reply(view.clocks, view.server_now)


def build_clocks_router(clocks: Clocks, ports: PortDirectory) -> APIRouter:
    """The routes of a task's stopwatch and timer."""
    router = APIRouter(prefix="/v1/tasks/{task_id}", tags=["clocks"])
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.post("/stopwatch/start")
    async def start_stopwatch(principal: person, task_id: UUID) -> ClocksReply:
        """Start the stopwatch in the task's column on the reader's board."""
        return reply_of(await clocks.start(principal, task_id))

    @router.post("/stopwatch/stop")
    async def stop_stopwatch(principal: person, task_id: UUID) -> ClocksReply:
        """Stop the stopwatch."""
        return reply_of(await clocks.stop(principal, task_id))

    @router.post("/stopwatch/reset")
    async def reset_stopwatch(principal: person, task_id: UUID) -> ClocksReply:
        """Clear the stopwatch."""
        return reply_of(await clocks.reset(principal, task_id))

    @router.put("/timer")
    async def set_timer(principal: person, task_id: UUID, body: TimerBody) -> ClocksReply:
        """Set the timer anew: the whole length from now."""
        return reply_of(await clocks.set_timer(principal, task_id, body.length_ms))

    @router.post("/timer/pause")
    async def pause_timer(principal: person, task_id: UUID) -> ClocksReply:
        """Pause the timer."""
        return reply_of(await clocks.hold_timer(principal, task_id, paused=True))

    @router.post("/timer/resume")
    async def resume_timer(principal: person, task_id: UUID) -> ClocksReply:
        """Let the timer go on."""
        return reply_of(await clocks.hold_timer(principal, task_id, paused=False))

    @router.delete("/timer")
    async def remove_timer(principal: person, task_id: UUID) -> ClocksReply:
        """Remove the timer."""
        return reply_of(await clocks.clear_timer(principal, task_id))

    return router
