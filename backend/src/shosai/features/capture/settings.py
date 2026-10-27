"""Capture's settings (`CAPTURE_*`), documented in `.env.example` section 2."""

from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.config.sections import SettingsSection


class CaptureSettings(SettingsSection):
    """Which Gemini Live model Leo's voice mode talks with (ADR 0070)."""

    # Модель Gemini Live голосового режима; голос Charon — решение владельца, не настройка.
    capture_voice_model: str = "gemini-3.8-live"

    def voice_model(self) -> ModelRef:
        """The voice mode's model, at Google."""
        return ModelRef(Provider.GOOGLE, self.capture_voice_model)
