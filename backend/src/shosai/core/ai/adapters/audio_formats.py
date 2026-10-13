"""The audio formats the speech providers take, named by the recording's media type."""

from typing import Final

# Провайдеры узнают формат по полю format или по расширению имени, а не по типу.
AUDIO_FORMATS: Final = {
    "audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav", "audio/mpeg": "mp3",
    "audio/mp3": "mp3", "audio/flac": "flac", "audio/mp4": "m4a", "audio/x-m4a": "m4a",
    "audio/ogg": "ogg", "audio/opus": "ogg", "audio/webm": "webm", "video/webm": "webm",
    "audio/aac": "aac",
}  # fmt: skip


def audio_format(media_type: str) -> str | None:
    """The format of a recording; None for a type no provider is known to take.

    A browser declares a recording as `audio/webm;codecs=opus`: the parameters are dropped.
    """
    return AUDIO_FORMATS.get(media_type.split(";", maxsplit=1)[0].strip().lower())
