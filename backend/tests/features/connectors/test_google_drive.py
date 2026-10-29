"""`FILE_SOURCES`, the scope picker and the Picker's setup over Google Drive's `drive.file`
(connectors plan step 12): a listing of picked files only, a changes page, an export, a file
over the bound, and the Picker's setup without a token."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select

from shosai.core.kernel.homes import Home
from shosai.core.kernel.tenancy import TenancyScope
from shosai.core.ports.directory import PortDirectory
from shosai.features.connectors.application.file_sources import ConnectorFileSources
from shosai.features.connectors.application.picker import (
    DrivePicker,
    PickerSetup,
    PickerUnavailableError,
)
from shosai.features.connectors.application.resources import Resources
from shosai.features.connectors.channels.http.picker_routes import build_picker_router
from shosai.features.connectors.contracts import CONNECTOR_USES, ConnectorUses
from shosai.features.connectors.contracts.files import FileQuery, FileTooLargeError
from shosai.features.connectors.contracts.resources import ResourceQuery
from shosai.features.connectors.domain.catalogue import App
from shosai.features.connectors.infrastructure.providers.google_drive import (
    FOLDER,
    GoogleDrive,
    GoogleDriveResources,
)
from shosai.features.connectors.infrastructure.store.records import ConnectionRecord
from shosai.features.identity.contracts import AUTHENTICATOR
from tests.core.web.probe_app import build_probe_app, client_of
from tests.features.billing.people_bench import BearerOfTheTest, bearer
from tests.features.connectors.google_bench import GoogleBench, google
from tests.features.connectors.provider_sessions import provider_access

__all__ = ["google"]

PICKED: list[dict[str, str | list[str]]] = [
    {"id": "doc-1", "name": "Plan", "mimeType": "application/vnd.google-apps.document",
     "modifiedTime": "2026-10-27T09:00:00.000Z", "parents": ["fold-1"], "version": "12",
     "webViewLink": "https://docs.google.com/document/d/doc-1"},
    {"id": "fold-1", "name": "Clients", "mimeType": FOLDER, "parents": ["root"]},
    {"id": "pdf-1", "name": "Contract.pdf", "mimeType": "application/pdf", "size": "2048"},
    {"id": "big-1", "name": "Archive.zip", "mimeType": "application/zip", "size": "99999999999"},
]  # fmt: skip


@dataclass
class DriveDouble:
    """www.googleapis.com/drive/v3 over the files the person picked."""

    calls: list[tuple[str, dict[str, list[str]]]] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        """One call to Drive."""
        url = urlsplit(str(request.url))
        query = parse_qs(url.query)
        path = url.path.removeprefix("/drive/v3")
        self.calls.append((path, query))
        if path == "/files":
            kind = query["q"][0]
            picked = [
                f for f in PICKED if f"mimeType = '{FOLDER}'" not in kind or f["mimeType"] == FOLDER
            ]
            return httpx.Response(200, json={"files": picked})
        if path == "/changes/startPageToken":
            return httpx.Response(200, json={"startPageToken": "40"})
        if path == "/changes":
            return httpx.Response(200, json={"newStartPageToken": "41", "changes": [
                {"fileId": "doc-1", "removed": False, "file": {**PICKED[0], "version": "13"}},
                {"fileId": "gone-1", "removed": True},
                {"fileId": "tr-1", "file": {"id": "tr-1", "name": "Old", "trashed": True}},
            ]})  # fmt: skip
        if path.endswith("/export"):
            return httpx.Response(200, content=b"Plan\nStep one")
        file_id = path.rsplit("/", 1)[1]
        if query.get("alt") == ["media"]:
            return httpx.Response(200, content=b"%PDF-1.7")
        found = [f for f in PICKED if f["id"] == file_id]
        return httpx.Response(200, json=found[0]) if found else httpx.Response(404)


@dataclass(frozen=True, slots=True)
class DriveBench:
    """Drive behind the ports, the picker and the Picker's route."""

    files: ConnectorFileSources
    resources: Resources
    api: DriveDouble
    google: GoogleBench
    http: httpx.AsyncClient


@pytest_asyncio.fixture
async def drive(google: GoogleBench, valkey: Redis) -> AsyncIterator[DriveBench]:
    """Google Drive with picked files, and the Picker configured."""
    api, adapter = DriveDouble(), GoogleDrive()
    ports = PortDirectory()
    ports.install([
        CONNECTOR_USES.bind(ConnectorUses("knowledge", frozenset({App.GOOGLE_DRIVE}))),
        AUTHENTICATOR.bind(BearerOfTheTest()),
    ])  # fmt: skip
    picker = DrivePicker(
        google.homes.transactions, PickerSetup("browser-key", "1234567890", "main-client")
    )
    app = build_probe_app(extra=(build_picker_router(picker, ports),)).app
    async with (
        provider_access(google, valkey, ("www.googleapis.com", api.handle)) as access,
        client_of(app, base_url="https://shosai.test") as http,
    ):
        yield DriveBench(
            ConnectorFileSources(access, {App.GOOGLE_DRIVE: adapter}),
            Resources(
                google.homes.transactions, access,
                {App.GOOGLE_DRIVE: GoogleDriveResources(adapter)},
            ),
            api, google, http,
        )  # fmt: skip


async def connected(bench: DriveBench) -> tuple[tuple[Home, uuid.UUID], uuid.UUID]:
    """A person with Drive connected, and the connection's id."""
    person = (Home.RU, uuid.uuid4())
    await bench.google.connect(person, App.GOOGLE_DRIVE)
    async with bench.google.homes.transactions.begin(TenancyScope(*person), read_only=True) as s:
        found: uuid.UUID | None = await s.scalar(select(ConnectionRecord.id))
    assert found is not None
    return person, found


async def test_a_listing_a_changes_page_and_an_export(drive: DriveBench) -> None:
    person, connection_id = await connected(drive)
    scope = TenancyScope(*person)

    page = await drive.files.browse(
        scope, connection_id, FileQuery(folder_id="fold-1", text="Pl'an")
    )
    start = await drive.files.changes(scope, connection_id, None, None)
    changes = await drive.files.changes(scope, connection_id, start.cursor, None)
    exported = await drive.files.content(scope, connection_id, "doc-1")
    downloaded = await drive.files.content(scope, connection_id, "pdf-1")
    with pytest.raises(FileTooLargeError):
        await drive.files.content(scope, connection_id, "big-1")

    assert [entry.id for entry in page.entries] == [f["id"] for f in PICKED]
    (path, listing), *_ = drive.api.calls
    assert path == "/files"
    assert listing["q"] == ["trashed = false and 'fold-1' in parents and name contains 'Pl\\'an'"]
    assert (start.cursor, changes.cursor) == ("40", "41")
    assert [entry.version for entry in changes.changed] == ["13"]
    assert changes.removed == ("gone-1", "tr-1")
    assert (exported.mime_type, exported.data) == ("text/plain", b"Plan\nStep one")
    assert downloaded.data == b"%PDF-1.7"
    assert not any(query.get("alt") == ["media"] for p, query in drive.api.calls if "big-1" in p)


async def test_the_scope_picker_lists_picked_folders(drive: DriveBench) -> None:
    person, _connection_id = await connected(drive)

    folders = await drive.resources.browse(
        TenancyScope(*person), App.GOOGLE_DRIVE, ResourceQuery(kind="folder", parent="root")
    )

    assert [(r.id, r.kind, r.has_children) for r in folders.items] == [("fold-1", "folder", True)]


async def test_the_picker_s_setup_names_the_account_and_never_a_token(drive: DriveBench) -> None:
    person, _connection_id = await connected(drive)
    stranger = (Home.RU, uuid.uuid4())

    setup = await drive.http.get("/v1/connectors/google_drive/picker", headers=bearer(person))
    refused = await drive.http.get("/v1/connectors/google_drive/picker", headers=bearer(stranger))

    assert setup.status_code == 200
    assert setup.json() == {
        "developer_key": "browser-key", "app_id": "1234567890", "client_id": "main-client",
        "login_hint": "anna@gmail.com",
    }  # fmt: skip
    assert "access" not in setup.text
    assert (refused.status_code, refused.json()["error"]["code"]) == (404, "not_connected")


async def test_an_unconfigured_picker_is_unavailable(drive: DriveBench) -> None:
    picker = DrivePicker(
        drive.google.homes.transactions, PickerSetup(None, "1234567890", "main-client")
    )

    with pytest.raises(PickerUnavailableError):
        await picker.config(TenancyScope(Home.RU, uuid.uuid4()))
