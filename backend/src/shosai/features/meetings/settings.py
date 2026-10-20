"""Meetings' settings (`MEETINGS_*`) and their production check (plan step 6, SM-5).

Until studio ships its `notes` and `transcript` roles (step 25), the findings and the
write-up are written by one model through OpenRouter, named by `MEETINGS_NOTES_MODEL`, and
recordings are transcribed by `MEETINGS_TRANSCRIBE_MODEL`, each with an optional fallback.
Outside development both are required. `ffprobe` and `ffmpeg` calls are bounded by
`MEETINGS_MEDIA_SECONDS` and `MEETINGS_MEDIA_MEMORY_MB` (MT-D10).
"""

from collections.abc import Iterator

from pydantic import PositiveInt

from shosai.core.config.gate import GateViolation
from shosai.core.config.loading import Settings
from shosai.core.config.sections import SettingsSection


class MeetingsSettings(SettingsSection):
    """Which model writes the notes of meetings."""

    # Модель OpenRouter для находок и записи Leo, например google/gemini-3.8-flash.
    meetings_notes_model: str | None = None
    # Запасная модель: ей переходит вызов, когда основная недоступна.
    meetings_notes_fallback_model: str | None = None
    # Модель OpenRouter для расшифровки записей с таймстемпами, например openai/whisper-large-v3.
    meetings_transcribe_model: str | None = None
    meetings_transcribe_fallback_model: str | None = None
    # Пределы одного вызова ffprobe или ffmpeg (MT-D10): секунды и мегабайты адресного пространства.
    meetings_media_seconds: PositiveInt = 300
    meetings_media_memory_mb: PositiveInt = 1024


def notes_model_set(settings: Settings) -> Iterator[GateViolation]:
    """Outside development a meeting's notes and recordings have their models."""
    meetings = settings.features.get(MeetingsSettings)
    if not meetings.meetings_notes_model:
        yield GateViolation(
            "MEETINGS_NOTES_MODEL", "без модели заметок встречи остаются без записи и находок"
        )
    if not meetings.meetings_transcribe_model:
        yield GateViolation(
            "MEETINGS_TRANSCRIBE_MODEL", "без модели расшифровки записи встреч не расшифровываются"
        )
