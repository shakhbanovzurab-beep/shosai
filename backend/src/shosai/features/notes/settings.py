"""The notes slice's settings (`NOTES_*`) and their production check (plan step 6, SM-5).

Until studio ships its `notes` and `transcript` roles (step 25), the findings and the
write-up are written by one model through OpenRouter, named by `NOTES_MODEL`, and
recordings are transcribed with their speakers by `NOTES_TRANSCRIBE_MODEL` (ADR 0073),
each with an optional fallback. Outside development both are required. `ffprobe` and
`ffmpeg` calls are bounded by `NOTES_MEDIA_SECONDS` and `NOTES_MEDIA_MEMORY_MB` (MT-D10).
"""

from collections.abc import Iterator

from pydantic import PositiveInt

from shosai.core.config.gate import GateViolation
from shosai.core.config.loading import Settings
from shosai.core.config.sections import SettingsSection


class NotesSettings(SettingsSection):
    """Which model writes the notes of meetings."""

    # Модель OpenRouter для находок и записи Leo, например google/gemini-3.8-flash.
    notes_model: str | None = None
    # Запасная модель: ей переходит вызов, когда основная недоступна.
    notes_fallback_model: str | None = None
    # Модель OpenRouter, которая расшифровывает записи с таймстемпами и говорящими,
    # например elevenlabs/scribe-v2 (ADR 0073).
    notes_transcribe_model: str | None = None
    # Запасная модель расшифровки; если она не размечает говорящих, строки будут без них.
    notes_transcribe_fallback_model: str | None = None
    # Пределы одного вызова ffprobe или ffmpeg (MT-D10): секунды и мегабайты адресного пространства.
    notes_media_seconds: PositiveInt = 300
    notes_media_memory_mb: PositiveInt = 1024


def notes_model_set(settings: Settings) -> Iterator[GateViolation]:
    """Outside development a meeting's notes and recordings have their models."""
    meetings = settings.features.get(NotesSettings)
    if not meetings.notes_model:
        yield GateViolation(
            "NOTES_MODEL", "без модели заметок встречи остаются без записи и находок"
        )
    if not meetings.notes_transcribe_model:
        yield GateViolation(
            "NOTES_TRANSCRIBE_MODEL", "без модели расшифровки записи встреч не расшифровываются"
        )
