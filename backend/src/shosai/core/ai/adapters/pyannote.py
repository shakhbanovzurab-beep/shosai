"""pyannote.ai: who spoke when in a recording (docs.pyannote.ai, read on 2026-10-13).

Four steps, all required:

1. `POST /media/input {url: media://<key>}` reserves a place in the provider's temporary
   storage and answers a presigned link
2. `PUT` of the audio to that link
3. `POST /diarize {url, model, numSpeakers}` starts the job and answers its `jobId`
4. `GET /jobs/{jobId}` until `succeeded`, `failed` or `canceled`, with
   `output.diarization [{speaker, start, end}]` in seconds

Through the provider's storage rather than a link to Shosai's bucket: the bucket is not open
to the internet, and a presigned link to a conversation is a worse trade than one upload.
The copy is removed by pyannote within 48 hours and cannot be deleted sooner (draft lesson).
The job is polled, not awaited on a webhook: its caller is a task with its own deadline, and
a webhook would need a public endpoint and a second delivery path for the same result.

pyannote charges a job once it is created, whatever its end, and reports no usage. The row
is the recording's seconds times the model's price. Every failure after the job was created
leaves as `PaidCallError`, so the port records the row before it reports the failure.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Final

import httpx
import structlog

from shosai.core.ai.adapters.audio_formats import audio_format
from shosai.core.ai.adapters.http_calls import Json, call_json
from shosai.core.ai.calls import ModelRef, Provider
from shosai.core.ai.errors import AiCallError, AiFailure, PaidCallError
from shosai.core.ai.requests import DiarizationRequest
from shosai.core.ai.results import Diarization, SpeakerTurn, Unit, Usage
from shosai.core.kernel.ids import new_id

PYANNOTE_API: Final = "https://api.pyannote.ai/v1"
API_TIMEOUT: Final = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=5.0)
# Запись в сотни мегабайт уходит минутами: запись тела ждём дольше коротких JSON-вызовов.
UPLOAD_TIMEOUT: Final = httpx.Timeout(connect=10.0, read=60.0, write=600.0, pool=5.0)
DONE: Final = frozenset({"succeeded", "failed", "canceled"})
log = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class JobPolling:
    """How the job is awaited: a growing pause between polls and a ceiling on the wait.

    A one-minute file is ready in seconds and an hour in minutes: a fixed short pause makes
    hundreds of polls of a long recording, a fixed long one idles a short one.
    """

    first_pause: float = 2.0
    growth: float = 1.4
    longest_pause: float = 15.0
    patience: float = 600.0
    # Часы и пауза подменяются в тестах: ожидание проверяется без реального времени.
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


def pyannote_client(api_key: str, base_url: str = PYANNOTE_API) -> httpx.AsyncClient:
    """The process's client of the pyannote API."""
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/") + "/",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=API_TIMEOUT,
        limits=httpx.Limits(max_connections=16, max_keepalive_connections=4, keepalive_expiry=60),
    )


def upload_client() -> httpx.AsyncClient:
    """The client of presigned uploads: no key goes to the storage behind the link."""
    return httpx.AsyncClient(
        timeout=UPLOAD_TIMEOUT,
        limits=httpx.Limits(max_connections=16, max_keepalive_connections=4, keepalive_expiry=60),
    )


def turns_of(job: Json) -> tuple[SpeakerTurn, ...]:
    """Speaker turns of a finished job; speakers numbered 0..N-1 by first appearance."""
    output = job.get("output")
    rows = output.get("diarization") if isinstance(output, dict) else None
    if not isinstance(rows, list):
        raise AiCallError(AiFailure.PROVIDER_ERROR)
    parsed = []
    for row in rows:
        start = row.get("start") if isinstance(row, dict) else None
        end = row.get("end") if isinstance(row, dict) else None
        label = row.get("speaker") if isinstance(row, dict) else None
        if not isinstance(start, int | float) or not isinstance(end, int | float):
            raise AiCallError(AiFailure.PROVIDER_ERROR)
        if end < start or not isinstance(label, str) or not label:
            raise AiCallError(AiFailure.PROVIDER_ERROR)
        parsed.append((round(start * 1000), round(end * 1000), label))
    parsed.sort()
    order: dict[str, int] = {}
    return tuple(
        SpeakerTurn(start_ms=start, end_ms=end, speaker=order.setdefault(label, len(order)))
        for start, end, label in parsed
    )


class Pyannote:
    """Splits recordings into speaker turns with pyannote's models."""

    def __init__(
        self,
        api: httpx.AsyncClient,
        uploads: httpx.AsyncClient,
        polling: JobPolling,
    ) -> None:
        self._api = api
        self._uploads = uploads
        self._polling = polling

    async def diarize(
        self, model: ModelRef, request: DiarizationRequest, deadline: timedelta | None
    ) -> Diarization:
        """Who spoke when; a failure after the job was created is `PaidCallError`."""
        format_name = audio_format(request.audio.media_type)
        if format_name is None:
            raise AiCallError(AiFailure.CONTENT_REFUSED)
        patience = self._polling.patience
        if deadline is not None:
            patience = min(patience, deadline.total_seconds())
        ends_at = self._polling.clock() + patience
        # Ключ — случайный: имя файла пользователя в чужой адрес не попадает.
        media = f"media://shosai/{new_id().hex}.{format_name}"
        reserved = await self._post("media/input", {"url": media})
        await self._upload(reserved.get("url"), request.audio.data, ends_at)
        body: Json = {"url": media, "model": model.model}
        if request.speakers is not None:
            body["numSpeakers"] = request.speakers
        job_id = (await self._post("diarize", body)).get("jobId")
        if not isinstance(job_id, str) or not job_id:
            raise AiCallError(AiFailure.PROVIDER_ERROR)
        usage = Usage(
            units=Decimal(str(round(request.audio.duration_seconds, 3))), unit=Unit.AUDIO_SECOND
        )
        try:
            job = await self._finished(job_id, ends_at)
            turns = turns_of(job)
        except AiCallError as error:
            log.warning("Разметка говорящих не удалась", job_id=job_id, failure=error.failure.value)
            raise PaidCallError(error.failure, usage) from None
        return Diarization(turns=turns, model=model, usage=usage)

    async def _post(self, path: str, body: Json) -> Json:
        return await call_json(
            self._api, Provider.PYANNOTE, self._api.build_request("POST", path, json=body)
        )

    async def _upload(self, link: object, data: bytes, ends_at: float) -> None:
        if not isinstance(link, str) or not link.startswith("https://"):
            raise AiCallError(AiFailure.PROVIDER_ERROR)
        if self._polling.clock() >= ends_at:
            raise AiCallError(AiFailure.DEADLINE_EXCEEDED)
        request = self._uploads.build_request(
            "PUT", link, content=data, headers={"Content-Type": "application/octet-stream"}
        )
        try:
            response = await self._uploads.send(request)
        except httpx.TimeoutException:
            raise AiCallError(AiFailure.DEADLINE_EXCEEDED) from None
        except httpx.TransportError:
            raise AiCallError(AiFailure.PROVIDER_ERROR) from None
        if not response.is_success:
            log.warning("Загрузка записи в pyannote отклонена", status=response.status_code)
            raise AiCallError(AiFailure.PROVIDER_ERROR)

    async def _finished(self, job_id: str, ends_at: float) -> Json:
        pause = self._polling.first_pause
        while True:
            job = await call_json(
                self._api, Provider.PYANNOTE, self._api.build_request("GET", f"jobs/{job_id}")
            )
            status = job.get("status")
            if status == "succeeded":
                return job
            if status in DONE:
                # Причина отказа может повторять запрос: в журнал — только статус.
                log.warning("Задание pyannote завершилось отказом", job_id=job_id, status=status)
                raise AiCallError(AiFailure.PROVIDER_ERROR)
            remaining = ends_at - self._polling.clock()
            if remaining <= 0:
                raise AiCallError(AiFailure.DEADLINE_EXCEEDED)
            await self._polling.sleep(min(pause, remaining))
            pause = min(pause * self._polling.growth, self._polling.longest_pause)
