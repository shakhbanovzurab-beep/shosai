"""`MAILBOXES` over Gmail against recorded answers (connectors plan step 11): a history gap
falls back to a list, a burst stays under quota, a send is never retried, and Gmail is
offered only to the owner's testers until public Gmail is turned on."""

import uuid

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.application.authorize import (
    Authorizer,
    AuthorizeTools,
    ConnectRequest,
    NotOfferedError,
)
from shosai.features.connectors.application.offers import GmailAccess, Offers
from shosai.features.connectors.contracts import CONNECTOR_USES, ConnectorUses
from shosai.features.connectors.contracts.mailboxes import (
    FolderKind,
    MailAddress,
    MailboxCursorExpiredError,
    MessageChange,
    MessageQuery,
    OutgoingMail,
)
from shosai.features.connectors.contracts.provider import (
    ProviderBusyError,
    ProviderUnavailableError,
)
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.domain.flows import ReturnKind, ReturnTarget
from shosai.features.connectors.infrastructure.oauth.flow_store import FlowStore
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord
from tests.features.connectors.connect_bench import BASE_URL
from tests.features.connectors.gmail_bench import GmailBench, gmail
from tests.features.connectors.google_bench import google

__all__ = ["gmail", "google"]


async def mailbox(bench: GmailBench) -> tuple[TenancyScope, uuid.UUID]:
    """A new person with Gmail connected, and the connection's id."""
    person = (Home.RU, uuid.uuid4())
    await bench.google.connect(person, App.GMAIL)
    scope = TenancyScope(*person)
    async with bench.google.homes.transactions.begin(scope, read_only=True) as session:
        found: uuid.UUID | None = await session.scalar(select(ConnectionRecord.id))
    assert found is not None
    return scope, found


async def test_labels_a_page_and_an_opened_message(gmail: GmailBench) -> None:
    scope, connection_id = await mailbox(gmail)

    folders = await gmail.mailboxes.folders(scope, connection_id)
    page = await gmail.mailboxes.messages(scope, connection_id, MessageQuery("INBOX", limit=2))
    opened = await gmail.mailboxes.message(scope, connection_id, "m1")

    assert [(f.id, f.kind) for f in folders] == [
        ("INBOX", FolderKind.INBOX), ("Label_7", FolderKind.LABEL),
    ]  # fmt: skip
    assert [m.id for m in page.messages] == ["m1", "m2"]
    assert page.next_page == "n2"
    first = page.messages[0]
    assert (first.subject, first.unread, first.has_attachments) == ("Contract", True, True)
    assert first.sender == MailAddress("boris@example.com", "Boris")
    assert (opened.body_text, opened.body_html) == ("Hi Anna\n", "<p>Hi Anna</p>")
    assert [(a.filename, a.size) for a in opened.attachments] == [("contract.pdf", 2048)]
    assert opened.message_id == "<m1@example.com>"


async def test_history_since_a_cursor_and_a_forgotten_one(gmail: GmailBench) -> None:
    scope, connection_id = await mailbox(gmail)

    start = await gmail.mailboxes.changes(scope, connection_id, None, None)
    later = await gmail.mailboxes.changes(scope, connection_id, "100", None)
    with pytest.raises(MailboxCursorExpiredError):
        await gmail.mailboxes.changes(scope, connection_id, "1", None)

    assert (start.cursor, start.changed) == ("100", ())
    assert (later.changed, later.removed, later.cursor) == (("m3", "m1"), ("m2",), "103")


async def test_a_burst_stays_under_the_quota(gmail: GmailBench) -> None:
    scope, connection_id = await mailbox(gmail)
    query = MessageQuery("INBOX", limit=2)

    await gmail.mailboxes.messages(scope, connection_id, query)
    await gmail.mailboxes.messages(scope, connection_id, query)
    with pytest.raises(ProviderBusyError):
        await gmail.mailboxes.messages(scope, connection_id, query)

    # Два прохода по 15 единиц исчерпали квоту в 30: третий список не ушёл в Gmail.
    assert [path for _m, path, _q, _b in gmail.api.calls].count("/messages") == 2


async def test_a_send_goes_once_and_drafts_and_flags_change(gmail: GmailBench) -> None:
    # У каждого ящика своя квота в 30 единиц: отправка, черновик и метки — в разных.
    scope, connection_id = await mailbox(gmail)
    drafts, flags = await mailbox(gmail), await mailbox(gmail)
    reply = OutgoingMail(
        to=(MailAddress("boris@example.com", "Boris"),), subject="Re: Contract",
        body_text="Signed.", thread_id="t1", in_reply_to="<m1@example.com>",
    )  # fmt: skip

    with pytest.raises(ProviderUnavailableError):
        await gmail.mailboxes.send(scope, connection_id, reply)
    draft = await gmail.mailboxes.save_draft(*drafts, reply, None)
    await gmail.mailboxes.change(*flags, ("m1",), MessageChange(
        remove_folders=("INBOX",), read=True, starred=True,
    ))  # fmt: skip

    sends = [body for _m, path, _q, body in gmail.api.calls if path == "/messages/send"]
    assert len(sends) == 1
    assert sends[0]["threadId"] == "t1"
    assert draft.id == "d1"
    (modify,) = [body for _m, path, _q, body in gmail.api.calls if path.endswith("batchModify")]
    assert modify == {
        "ids": ["m1"],
        "addLabelIds": ["STARRED"],
        "removeLabelIds": ["INBOX", "UNREAD"],
    }


async def test_gmail_is_offered_only_to_testers_while_public_gmail_is_off(
    gmail: GmailBench, valkey: Redis
) -> None:
    tester, stranger = uuid.uuid4(), uuid.uuid4()
    registry, _outbox = gmail.google.wiring
    ports = PortDirectory()
    ports.install(
        [CONNECTOR_USES.bind(ConnectorUses("mail", frozenset({App.GMAIL, App.GOOGLE_CALENDAR})))]
    )
    offers = Offers(ports, registry, GmailAccess(public=False, testers=frozenset({tester})))
    tools = AuthorizeTools(offers, registry, FlowStore(valkey), BASE_URL, sealing=True)
    authorizer = Authorizer(gmail.google.homes.transactions, tools)
    popup = ReturnTarget(ReturnKind.POPUP)

    assert App.GMAIL in offers.offered(tester)
    assert App.GMAIL not in offers.offered(stranger)
    assert App.GOOGLE_CALENDAR in offers.offered(stranger)
    with pytest.raises(NotOfferedError):
        await authorizer.begin(ConnectRequest(stranger, Home.RU, App.GMAIL, popup))
    started = await authorizer.begin(ConnectRequest(tester, Home.RU, App.GMAIL, popup))
    assert "gmail.modify" in started.authorize_url
