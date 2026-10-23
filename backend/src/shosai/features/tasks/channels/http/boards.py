"""A person's boards (`/v1/boards*`; tasks plan §3.3, §3.14).

The list with the incoming board, a board made from a template in the request's language,
a board's read, change, layout and deletion, and the incoming board's choice. Jira's routes
answer as without a connection until steps 12 and 13. Errors use the platform's envelope with
the codes the cabinet words: `board_not_found`, `name_required`, `name_too_long`,
`title_required`, `title_too_long`, `boards_full`, `board_changed`, `connect_jira_first`,
`not_jira_board`, `validation_error`.
"""

from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response

from shosai.core.i18n.locales import parse_accept_language
from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.contracts import Principal, bearer_principal
from shosai.features.tasks.application.board_reads import BoardReads
from shosai.features.tasks.application.boards import BoardWrites
from shosai.features.tasks.channels.http.board_models import (
    BoardCreateBody,
    BoardDetailOut,
    BoardPatchBody,
    BoardsOut,
    BoardSummaryOut,
    IncomingBody,
    JiraAvailableOut,
    JiraConnectBody,
    LayoutBody,
)
from shosai.features.tasks.channels.http.board_shapes import (
    board_out,
    boards_out,
    layout_of,
    summary_out,
)
from shosai.features.tasks.channels.http.shapes import invalid


def build_boards_router(
    services: tuple[BoardReads, BoardWrites], ports: PortDirectory
) -> APIRouter:
    """The routes of the person's boards."""
    router = APIRouter(prefix="/v1/boards", tags=["boards"])
    _list_routes(router, services, ports)
    _board_routes(router, services, ports)
    return router


def _list_routes(
    router: APIRouter, services: tuple[BoardReads, BoardWrites], ports: PortDirectory
) -> None:
    reads, writes = services
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.get("")
    async def list_boards(principal: person) -> BoardsOut:
        """The person's boards and the incoming work waiting for a board."""
        return boards_out(await reads.boards(principal))

    @router.post("", status_code=HTTPStatus.CREATED)
    async def create_board(
        principal: person,
        body: BoardCreateBody,
        accept_language: Annotated[str | None, Header()] = None,
    ) -> BoardSummaryOut:
        """A board from a template, its columns named in the request's language."""
        language = parse_accept_language(accept_language)
        made = (body.name, body.icon, body.template)
        return summary_out(await writes.create(principal, made, language))

    @router.put("/incoming")
    async def choose_incoming(principal: person, body: IncomingBody) -> BoardsOut:
        """Choose the board incoming work lands on, or none."""
        return boards_out(await writes.set_incoming(principal, body.board_id))

    @router.get("/jira/available")
    async def jira_boards(principal: person) -> JiraAvailableOut:
        """The Jira boards the person may sync: none until Jira is connected (steps 12, 13)."""
        del principal
        return JiraAvailableOut(connected=False, account=None, items=[])

    @router.post("/jira", status_code=HTTPStatus.CREATED)
    async def connect_jira_board(principal: person, body: JiraConnectBody) -> BoardSummaryOut:
        """Sync a Jira board: Jira must be connected first (steps 12, 13)."""
        del principal, body
        raise AppError("connect_jira_first", HTTPStatus.CONFLICT)


def _board_routes(
    router: APIRouter, services: tuple[BoardReads, BoardWrites], ports: PortDirectory
) -> None:
    reads, writes = services
    person = Annotated[Principal, Depends(bearer_principal(ports))]

    @router.get("/{board_id}")
    async def read_board(principal: person, board_id: UUID) -> BoardDetailOut:
        """The board with its columns and cards."""
        return board_out(await reads.detail(principal, board_id))

    @router.patch("/{board_id}")
    async def change_board(
        principal: person, board_id: UUID, body: BoardPatchBody
    ) -> BoardSummaryOut:
        """Rename the board or change its icon."""
        if any(getattr(body, name) is None for name in body.model_fields_set):
            raise invalid()
        return summary_out(await writes.change(principal, board_id, (body.name, body.icon)))

    @router.delete("/{board_id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_board(principal: person, board_id: UUID) -> Response:
        """Delete the board and the hand-made tasks on it (TK-D6)."""
        await writes.delete(principal, board_id)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.put("/{board_id}/layout", status_code=HTTPStatus.NO_CONTENT)
    async def lay_out_board(principal: person, board_id: UUID, body: LayoutBody) -> Response:
        """Reorder and rename the columns and the cards the board shows."""
        await writes.lay_out(principal, board_id, layout_of(body))
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @router.post("/{board_id}/sync")
    async def sync_board(principal: person, board_id: UUID) -> BoardSummaryOut:
        """Take the latest from Jira now; an app board has nothing to sync."""
        await reads.owned(principal, board_id)
        raise AppError("not_jira_board", HTTPStatus.CONFLICT)
