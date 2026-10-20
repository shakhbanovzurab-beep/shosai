"""`ffprobe` and `ffmpeg` as subprocesses that only fail themselves (MT-D10).

Each call runs under `prlimit` with an address-space cap and a CPU-time cap, within a
wall-clock limit after which it is killed, with an environment of `PATH` alone and
`-protocol_whitelist file`, so a tool reads and writes local files and opens no network;
it runs in a process group of its own, killed whole when its time is up.
A crash, a hostile file, a call past its time or one past its memory ends that process
and raises `MediaError(media_unreadable)`; the worker goes on. `probe` reads the header
only, so a format outside the allowed list is refused before any decoder runs.
"""

import asyncio
import contextlib
import json
import os
import re
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import structlog

from shosai.features.meetings.domain.recordings import MediaFacts, Part

UNREADABLE: Final = "media_unreadable"
UNSUPPORTED: Final = "unsupported_audio_format"
SILENCE: Final = re.compile(r"silence_(start|end): (-?\d+(?:\.\d+)?)")
# Части — моно 16 кГц Opus в Ogg: речь разборчива, 5 минут — около 1 МБ.
PART_ENCODING: Final = ("-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "24k", "-f", "ogg")
PART_MEDIA_TYPE: Final = "audio/ogg"
log = structlog.stdlib.get_logger(__name__)


class MediaError(Exception):
    """A recording that cannot be read; `code` is the run's error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class MediaLimits:
    """What one tool call may take: seconds of wall clock and megabytes of address space."""

    seconds: int
    memory_mb: int


class MediaTools:
    """The two tools, bounded per call."""

    def __init__(self, limits: MediaLimits, tools: tuple[str, str] = ("ffprobe", "ffmpeg")) -> None:
        self._limits = limits
        self._probe, self._ffmpeg = tools

    async def _run(self, command: list[str]) -> str:
        """The tool's standard error and output, or `MediaError` when it failed in any way."""
        limits = self._limits
        bounded = [
            "prlimit", f"--as={limits.memory_mb * 1024 * 1024}", f"--cpu={limits.seconds}",
            "--nofile=64", "--", *command,
        ]  # fmt: skip
        process = await asyncio.create_subprocess_exec(
            *bounded,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin"},
            # Своя группа процессов: по сроку убивается инструмент вместе с его потомками.
            start_new_session=True,
        )
        try:
            out, err = await asyncio.wait_for(process.communicate(), timeout=limits.seconds)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            await process.communicate()
            log.warning("Инструмент медиа не уложился во время", tool=command[0])
            raise MediaError(UNREADABLE) from None
        if process.returncode != 0:
            log.warning(
                "Инструмент медиа завершился с ошибкой", tool=command[0], code=process.returncode
            )
            raise MediaError(UNREADABLE)
        return out.decode(errors="replace") + err.decode(errors="replace")

    async def probe(self, path: Path) -> MediaFacts:
        """The container, the first audio stream's codec and the duration, from the header."""
        output = await self._run(
            [
                self._probe, "-v", "error", "-protocol_whitelist", "file", "-print_format", "json",
                "-show_entries", "format=format_name,duration:stream=codec_type,codec_name",
                str(path),
            ]
        )  # fmt: skip
        try:
            found = json.loads(output)
            audio = [s for s in found.get("streams", []) if s.get("codec_type") == "audio"]
            containers = tuple(str(found["format"]["format_name"]).split(","))
            duration_ms = round(float(found["format"].get("duration") or 0) * 1000)
        except (ValueError, KeyError, TypeError) as error:
            raise MediaError(UNREADABLE) from error
        codec = str(audio[0]["codec_name"]) if audio else None
        return MediaFacts(containers, codec, duration_ms)

    async def silences(self, path: Path) -> list[int]:
        """The middles of the recording's pauses of half a second or more, in milliseconds."""
        output = await self._run(
            [
                self._ffmpeg, "-nostdin", "-hide_banner", "-protocol_whitelist", "file",
                "-i", str(path), "-vn", "-af", "silencedetect=noise=-30dB:d=0.5", "-f", "null", "-",
            ]
        )  # fmt: skip
        moments: list[int] = []
        start: float | None = None
        for kind, value in SILENCE.findall(output):
            if kind == "start":
                start = float(value)
            elif start is not None:
                moments.append(round((start + float(value)) / 2 * 1000))
                start = None
        return moments

    async def cut(self, path: Path, part: Part, target: Path) -> Path:
        """The part's audio alone, mono Opus at 16 kHz, written to `target`."""
        await self._run(
            [
                self._ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-y",
                "-protocol_whitelist", "file", "-ss", f"{part.start_ms / 1000:.3f}",
                "-t", f"{part.duration_ms / 1000:.3f}", "-i", str(path), "-vn",
                *PART_ENCODING, str(target),
            ]
        )  # fmt: skip
        return target
