"""A recording before it is transcribed (MT-D10): what may be read, how long, how it is cut.

Only containers and audio codecs on the allowed list are decoded: `ffprobe` names both
first, and anything else is refused (`unsupported_audio_format`) before a decoder runs. A
recording longer than 6 hours is refused (`recording_too_long`). The audio is cut into
parts of at most 5 minutes — a speech provider takes at most 25 MB and answers within 60
s — each ending in the latest silence after its first minute, or at the 5 minutes when
the speech never pauses.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

RECORDING_MAX_MS: Final = 6 * 3600 * 1000
PART_MAX_MS: Final = 5 * 60 * 1000
PART_MIN_MS: Final = 60 * 1000
# Контейнеры по именам ffprobe: format_name — список через запятую, достаточно одного.
CONTAINERS: Final = frozenset(
    {"mov", "mp4", "m4a", "3gp", "matroska", "webm", "mp3", "wav", "ogg", "flac", "aac"}
)
AUDIO_CODECS: Final = frozenset(
    {
        "aac", "mp3", "opus", "vorbis", "flac", "alac", "pcm_s16le", "pcm_s24le",
        "pcm_s32le", "pcm_f32le", "pcm_u8",
    }
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class MediaFacts:
    """What `ffprobe` read from a recording's header."""

    containers: tuple[str, ...]
    audio_codec: str | None
    duration_ms: int


@dataclass(frozen=True, slots=True)
class Part:
    """A stretch of the recording to transcribe alone: its start and end in milliseconds."""

    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        """The part's length."""
        return self.end_ms - self.start_ms


def readable(facts: MediaFacts) -> bool:
    """Whether the recording's container and audio codec are on the allowed list."""
    return bool(CONTAINERS.intersection(facts.containers)) and facts.audio_codec in AUDIO_CODECS


def too_long(duration_ms: int) -> bool:
    """Whether the recording is longer than a meeting may be (6 hours)."""
    return duration_ms > RECORDING_MAX_MS


def parts_of(duration_ms: int, silences: Sequence[int]) -> list[Part]:
    """Parts of at most 5 minutes covering the recording, cut at silences where there are.

    `silences` are moments of silence in milliseconds; a part ends at the latest one after
    its first minute and within its 5 minutes, else at the 5 minutes.
    """
    if duration_ms <= 0:
        return []
    quiet = sorted(set(silences))
    parts: list[Part] = []
    start = 0
    while duration_ms - start > PART_MAX_MS:
        limit = start + PART_MAX_MS
        fits = [moment for moment in quiet if start + PART_MIN_MS <= moment <= limit]
        end = fits[-1] if fits else limit
        parts.append(Part(start, end))
        start = end
    parts.append(Part(start, duration_ms))
    return parts
