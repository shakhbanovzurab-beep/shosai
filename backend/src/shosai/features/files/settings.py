"""Files' settings (`FILES_*`) and their production check (files plan FL-D9).

`FILES_DOWNLOAD_BASE_URL` is the edge's address that streams downloads from the homes'
buckets with `nosniff` and a sandbox (ADR 0055 point 8), for example
`https://shosai.tech/dl`. Locally, without an edge, it may stay empty: links then point
straight at the bucket. Outside development it is required.
"""

from collections.abc import Iterator

from pydantic import HttpUrl

from shosai.core.config.gate import GateViolation
from shosai.core.config.loading import Settings
from shosai.core.config.sections import SettingsSection


class FilesSettings(SettingsSection):
    """Where downloads are served from."""

    # Адрес edge для скачивания: {база}/{дом}/{путь подписанной ссылки бакета}.
    files_download_base_url: HttpUrl | None = None


def downloads_through_edge(settings: Settings) -> Iterator[GateViolation]:
    """Outside development every download goes through the edge (FL-D9)."""
    if settings.features.get(FilesSettings).files_download_base_url is None:
        yield GateViolation(
            "FILES_DOWNLOAD_BASE_URL", "без адреса edge файлы отдаются без nosniff и песочницы"
        )
