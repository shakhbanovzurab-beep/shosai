"""pyannote.ai as a transport double: the media reservation, the upload, the job and its polls.

The real adapter runs against it with no network. A test scripts the job's statuses in order
and the output of a succeeded job; every request is recorded with its headers.
"""

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from shosai.core.ai.adapters.pyannote import PYANNOTE_API

type Json = dict[str, Any]
UPLOAD_LINK = "https://storage.pyannote.example/upload/probe?signature=probe"


@dataclass
class ScriptedPyannote:
    """Scripted job statuses and failures; the requests it received."""

    statuses: list[str] = field(default_factory=lambda: ["running", "succeeded"])
    turns: list[Json] = field(default_factory=list)
    failing: dict[str, int] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)

    def api_client(self) -> httpx.AsyncClient:
        """The API client, authorised as the adapter's own is."""
        return httpx.AsyncClient(
            base_url=PYANNOTE_API + "/",
            headers={"Authorization": "Bearer probe-key"},
            transport=httpx.MockTransport(self._handle),
        )

    def upload_client(self) -> httpx.AsyncClient:
        """The client of presigned uploads."""
        return httpx.AsyncClient(transport=httpx.MockTransport(self._handle))

    def sent(self, method: str, path: str) -> list[httpx.Request]:
        """The requests of a method to a path ending as given."""
        return [r for r in self.requests if r.method == method and r.url.path.endswith(path)]

    def body(self, method: str, path: str) -> Json:
        """The JSON body of the first such request."""
        loaded = json.loads(self.sent(method, path)[0].content)
        assert isinstance(loaded, dict)
        return loaded

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        step = request.url.path.rsplit("/", 1)[-1] if request.method != "GET" else "jobs"
        if step in self.failing:
            return httpx.Response(self.failing[step], json={"message": "scripted failure"})
        if request.method == "PUT":
            return httpx.Response(200)
        if step == "input":
            return httpx.Response(200, json={"url": UPLOAD_LINK})
        if step == "diarize":
            return httpx.Response(200, json={"jobId": "job-1", "status": "created"})
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        job: Json = {"jobId": "job-1", "status": status}
        if status == "succeeded":
            job["output"] = {"diarization": self.turns}
        if status == "failed":
            job["output"] = {"error": "audio could not be decoded"}
        return httpx.Response(200, json=job)
