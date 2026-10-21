"""The transcript archive of benches without a bucket: none of their meetings is archived."""

from typing import Final

from shosai.features.notes.infrastructure.transcript_archive import TranscriptArchive

NO_ARCHIVE: Final = TranscriptArchive({})
