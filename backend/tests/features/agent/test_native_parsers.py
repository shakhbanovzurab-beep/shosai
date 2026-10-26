"""The proxy's stream read the way the shipped parsers read it (agent step 14).

macOS 1.4.5 (`StreamingParser.swift`) reads the body with `bytes.lines`, which also breaks a
line on U+2028, U+2029 and U+0085; Windows 1.4.5 (`StreamingParser.cs`) with `ReadLineAsync`.
Both keep the lines that start with `data:`, trim them, stop at `[DONE]`, skip what does not
decode, read `choices[0].delta.content` and stop reading at the finish `stop`. Each is replayed
here on the proxy's answer, with text that would split a raw line on macOS.
"""

import json
import re
import uuid
from typing import Final

from shosai.core.ai.errors import AiCallError, AiFailure
from shosai.core.ai.results import ChatDelta
from tests.features.agent.proxy_bench import CHAT, MACOS, MODEL, WINDOWS, ProxyBench, spoken
from tests.features.agent.turn_bench import HOME
from tests.features.billing.people_bench import bearer

MACOS_LINES: Final = re.compile("\r\n|[\n\r  \u0085]")
WINDOWS_LINES: Final = re.compile("\r\n|[\n\r]")
TRICKY: Final = ("Price:  €40", " next\u0085line", " — да.")


def replayed(body: str, lines: re.Pattern[str]) -> tuple[str, str | None]:
    """What a parser shows, and the finish it stopped at."""
    shown: list[str] = []
    for line in lines.split(body):
        if not line.startswith("data:"):
            continue
        payload = line.removeprefix("data:").strip()
        if not payload:
            continue
        if payload == "[DONE]":
            return "".join(shown), None
        try:
            choice = json.loads(payload)["choices"][0]
        except ValueError, KeyError, IndexError:
            continue
        shown.append(choice["delta"].get("content") or "")
        if choice.get("finish_reason") == "stop":
            return "".join(shown), "stop"
    return "".join(shown), None


async def test_both_parsers_read_the_whole_answer_and_stop_at_its_finish(
    proxy_bench: ProxyBench,
) -> None:
    proxy_bench.model.pieces = spoken(*TRICKY)
    person = uuid.uuid4()

    mac = await proxy_bench.http.post(CHAT, json=MACOS, headers=bearer((HOME, person)))
    win = await proxy_bench.http.post(CHAT, json=WINDOWS, headers=bearer((HOME, person)))

    expected = ("".join(TRICKY), "stop")
    assert replayed(mac.content.decode(), MACOS_LINES) == expected
    assert replayed(win.content.decode(), WINDOWS_LINES) == expected


async def test_a_broken_answer_shows_its_note_and_ends_at_done(proxy_bench: ProxyBench) -> None:
    proxy_bench.model.pieces = [ChatDelta(text="Partly", model=MODEL)]
    proxy_bench.model.failure = AiCallError(AiFailure.PROVIDER_ERROR)

    answer = await proxy_bench.http.post(CHAT, json=MACOS, headers=bearer((HOME, uuid.uuid4())))

    for lines in (MACOS_LINES, WINDOWS_LINES):
        shown, finish = replayed(answer.content.decode(), lines)
        assert (shown, finish) == ("Partly\n[The answer was interrupted. Try again.]", None)
