"""Meetings' settings (`MEETINGS_*`) and their production check (plan step 6, SM-5).

Until studio ships its `notes` role (step 25), the findings and the write-up are written by
one model through OpenRouter, named by `MEETINGS_NOTES_MODEL`, with an optional fallback.
Outside development the model is required: without it no meeting would get its notes.
"""

from collections.abc import Iterator

from shosai.core.config.gate import GateViolation
from shosai.core.config.loading import Settings
from shosai.core.config.sections import SettingsSection


class MeetingsSettings(SettingsSection):
    """Which model writes the notes of meetings."""

    # Модель OpenRouter для находок и записи Leo, например google/gemini-3.8-flash.
    meetings_notes_model: str | None = None
    # Запасная модель: ей переходит вызов, когда основная недоступна.
    meetings_notes_fallback_model: str | None = None


def notes_model_set(settings: Settings) -> Iterator[GateViolation]:
    """Outside development a meeting's notes have a model to write them."""
    if not settings.features.get(MeetingsSettings).meetings_notes_model:
        yield GateViolation(
            "MEETINGS_NOTES_MODEL", "без модели заметок встречи остаются без записи и находок"
        )
