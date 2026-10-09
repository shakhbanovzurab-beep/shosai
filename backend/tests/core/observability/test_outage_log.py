"""The outage log: the first failure at once, then one line per interval with a count."""

from datetime import timedelta

from structlog.testing import capture_logs

from shosai.core.observability.outage_log import OutageLog


class ManualClock:
    """A monotonic clock a test moves by hand."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_failures_are_logged_at_most_once_per_interval() -> None:
    clock = ManualClock()
    outages = OutageLog("Кэш не ответил", timedelta(seconds=10), clock)

    with capture_logs() as lines:
        outages.failed(TimeoutError(), operation="get")
        for _ in range(5):
            clock.now += 1
            outages.failed(ConnectionError("refused"), operation="get")
        clock.now += 10
        outages.failed(ConnectionError("refused"), operation="set")

    assert [(line["event"], line["log_level"]) for line in lines] == [
        ("Кэш не ответил", "warning"),
        ("Кэш не ответил", "warning"),
    ]
    first, second = lines
    assert (first["error_type"], first["held_back"], first["operation"]) == (
        "TimeoutError",
        0,
        "get",
    )
    assert (second["error_type"], second["held_back"]) == ("ConnectionError", 5)
    assert second["failure"] == "refused"


def test_a_long_error_text_is_cut() -> None:
    outages = OutageLog("Хранилище не ответило")

    with capture_logs() as lines:
        outages.failed(OSError("x" * 1000))

    assert len(lines[0]["failure"]) == 200
