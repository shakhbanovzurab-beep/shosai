"""Google Drive on `FILE_SOURCES` and `RESOURCES` over `drive.file` (API v3, plan step 12).

With `drive.file`, Drive itself shows Shosai only the files the person picked in Google's
Picker and the files Shosai created: a listing never holds anything else, whatever it asks.
Changes follow a page token from `changes.getStartPageToken`; trashed files count as removed.
Google's own documents are exported as text — a document and a presentation as plain text, a
spreadsheet as CSV — and any other file is downloaded whole while it is under the bound.
"""

from datetime import datetime
from http import HTTPStatus
from typing import Any, Final
from urllib.parse import quote

from shosai.features.connectors.contracts.files import (
    MAX_CONTENT_BYTES,
    FileChanges,
    FileContent,
    FileEntry,
    FileNotFoundAtProviderError,
    FilePage,
    FileQuery,
    FileTooLargeError,
)
from shosai.features.connectors.contracts.provider import (
    ProviderBusyError,
    ProviderCall,
    ProviderRefusedError,
    ProviderResponse,
    ProviderSession,
)
from shosai.features.connectors.contracts.resources import Resource, ResourcePage, ResourceQuery

API: Final = "https://www.googleapis.com/drive/v3"
FOLDER: Final = "application/vnd.google-apps.folder"
NATIVE: Final = "application/vnd.google-apps."
EXPORTS: Final = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.presentation": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
}  # fmt: skip
FIELDS: Final = "id,name,mimeType,size,modifiedTime,parents,webViewLink,version,trashed"
SHARED_DRIVES: Final = {"supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
RATE_REASONS: Final = frozenset({"rateLimitExceeded", "userRateLimitExceeded"})


def _checked(response: ProviderResponse) -> ProviderResponse:
    if HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES:
        return response
    if response.status == HTTPStatus.NOT_FOUND:
        raise FileNotFoundAtProviderError
    body = response.json() if response.body else {}
    error = body.get("error") if isinstance(body, dict) else None
    errors = error.get("errors") if isinstance(error, dict) else None
    reason = errors[0].get("reason") if isinstance(errors, list) and errors else None
    if response.status == HTTPStatus.FORBIDDEN and reason in RATE_REASONS:
        raise ProviderBusyError(30)
    raise ProviderRefusedError(response.status, reason if isinstance(reason, str) else None)


def _object(response: ProviderResponse) -> dict[str, Any]:
    body = _checked(response).json()
    if not isinstance(body, dict):
        raise ProviderRefusedError(response.status, "not_an_object")
    return body


def moment(value: str) -> datetime:
    """An RFC 3339 moment of Drive's answers."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def entry_of(item: dict[str, Any]) -> FileEntry:
    """One file of Drive's shape."""
    size, modified = item.get("size"), item.get("modifiedTime")
    parents = item.get("parents")
    return FileEntry(
        id=str(item["id"]), name=str(item.get("name", "")),
        mime_type=str(item.get("mimeType", "application/octet-stream")),
        is_folder=item.get("mimeType") == FOLDER,
        size=int(size) if isinstance(size, str) and size.isdigit() else None,
        modified_at=moment(modified) if isinstance(modified, str) else None,
        parent_ids=tuple(str(p) for p in parents) if isinstance(parents, list) else (),
        web_url=item.get("webViewLink"), version=item.get("version"),
    )  # fmt: skip


def _quoted(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def search_of(query: FileQuery, kind: str | None = None) -> str:
    """Drive's `q` for a folder, a name and a kind; trashed files never."""
    terms = ["trashed = false"]
    if query.folder_id:
        terms.append(f"'{_quoted(query.folder_id)}' in parents")
    if query.text:
        terms.append(f"name contains '{_quoted(query.text)}'")
    if kind == "folder":
        terms.append(f"mimeType = '{FOLDER}'")
    elif kind == "file":
        terms.append(f"mimeType != '{FOLDER}'")
    return " and ".join(terms)


class GoogleDrive:
    """The drive adapter of Google Drive."""

    async def browse(
        self, session: ProviderSession, query: FileQuery, kind: str | None = None
    ) -> FilePage:
        """A page of the files the person picked or Shosai created."""
        params = {
            "q": search_of(query, kind), "pageSize": str(query.limit), "spaces": "drive",
            "fields": f"nextPageToken,files({FIELDS})", **SHARED_DRIVES,
        } | ({"pageToken": query.page} if query.page else {})  # fmt: skip
        body = _object(await session.request(
            ProviderCall("GET", "knowledge.list_files", f"{API}/files", params=params)
        ))  # fmt: skip
        files = [item for item in body.get("files", []) if isinstance(item, dict)]
        return FilePage(tuple(entry_of(item) for item in files), body.get("nextPageToken"))

    async def changes(
        self, session: ProviderSession, cursor: str | None, page: str | None
    ) -> FileChanges:
        """Changes since the cursor; without one, the drive's current cursor."""
        if cursor is None and page is None:
            start = _object(await session.request(ProviderCall(
                "GET", "knowledge.start_changes", f"{API}/changes/startPageToken",
                params={"supportsAllDrives": "true"},
            )))  # fmt: skip
            return FileChanges((), (), None, str(start["startPageToken"]))
        params = {
            "pageToken": str(page or cursor), "spaces": "drive", **SHARED_DRIVES,
            "fields": f"nextPageToken,newStartPageToken,changes(fileId,removed,file({FIELDS}))",
        }  # fmt: skip
        body = _object(await session.request(
            ProviderCall("GET", "knowledge.file_changes", f"{API}/changes", params=params)
        ))  # fmt: skip
        changed: list[FileEntry] = []
        removed: list[str] = []
        for change in body.get("changes", []):
            item = change.get("file")
            if change.get("removed") or not isinstance(item, dict) or item.get("trashed"):
                removed.append(str(change.get("fileId")))
            else:
                changed.append(entry_of(item))
        next_page = body.get("nextPageToken")
        return FileChanges(
            tuple(changed), tuple(removed), next_page,
            None if next_page else body.get("newStartPageToken"),
        )  # fmt: skip

    async def content(self, session: ProviderSession, file_id: str) -> FileContent:
        """A Google document as text, any other file downloaded under the bound."""
        url = f"{API}/files/{quote(file_id, safe='')}"
        meta = _object(await session.request(ProviderCall(
            "GET", "knowledge.read_file", url, params={"fields": "id,name,mimeType,size",
                                                       "supportsAllDrives": "true"},
        )))  # fmt: skip
        mime, size = str(meta.get("mimeType", "")), meta.get("size")
        if mime.startswith(NATIVE):
            target = EXPORTS.get(mime)
            if target is None:
                raise ProviderRefusedError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "not_exportable")
            call = ProviderCall("GET", "knowledge.export_file", f"{url}/export",
                                params={"mimeType": target})  # fmt: skip
        else:
            if isinstance(size, str) and size.isdigit() and int(size) > MAX_CONTENT_BYTES:
                raise FileTooLargeError
            target = mime
            call = ProviderCall("GET", "knowledge.download_file", url,
                                params={"alt": "media", "supportsAllDrives": "true"})  # fmt: skip
        data = _checked(await session.request(call)).body
        if len(data) > MAX_CONTENT_BYTES:
            raise FileTooLargeError
        return FileContent(file_id, str(meta.get("name", "")), target, data)


class GoogleDriveResources:
    """The scope picker's view of Drive: the picked files and folders."""

    def __init__(self, drive: GoogleDrive) -> None:
        self._drive = drive

    @property
    def kinds(self) -> frozenset[str]:
        """Files and folders."""
        return frozenset({"file", "folder"})

    async def browse(self, session: ProviderSession, query: ResourceQuery) -> ResourcePage:
        """A page of picked places of the query's kind."""
        files = FileQuery(
            folder_id=query.parent, text=query.text, page=query.cursor, limit=query.limit
        )
        page = await self._drive.browse(session, files, query.kind)
        return ResourcePage(
            tuple(
                Resource(
                    id=entry.id, name=entry.name, kind="folder" if entry.is_folder else "file",
                    parent_id=entry.parent_ids[0] if entry.parent_ids else None,
                    has_children=entry.is_folder, url=entry.web_url,
                )
                for entry in page.entries
            ),
            page.next_page,
        )  # fmt: skip
