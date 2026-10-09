"""No secret value reaches a log line, whatever the key, depth or logging API (§16.8)."""

import logging

import pytest
import structlog
from hypothesis import given
from hypothesis import strategies as st
from pydantic import SecretStr

from shosai.core.config.loading import load_settings
from shosai.core.observability.redaction import (
    MAX_DEPTH,
    REDACTED,
    SENSITIVE_KEYS,
    SENSITIVE_SUFFIXES,
    TRUNCATED,
    is_sensitive_key,
    redact_value,
)
from tests.core.config.sample_environ import SAMPLE_FERNET_KEY, SAMPLE_SECRET, production_environ
from tests.core.observability.capture import captured_logs

log = structlog.stdlib.get_logger("tests.redaction")
secrets = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=12, max_size=32).map(
    lambda text: f"zq{text}"
)
plain_keys = st.sampled_from(["detail", "payload", "context", "items", "headers", "extra"])


@st.composite
def sensitive_keys(draw: st.DrawFn) -> str:
    """A sensitive key as code writes it: any case, dashes or underscores, a known suffix."""
    exact = st.sampled_from(sorted(SENSITIVE_KEYS))
    suffixed = st.builds(
        lambda stem, suffix: f"{stem}{suffix}",
        st.sampled_from(["s3", "client", "openrouter", "x"]),
        st.sampled_from(SENSITIVE_SUFFIXES),
    )
    key = draw(st.one_of(exact, suffixed))
    upper = draw(st.booleans())
    dashed = draw(st.booleans())
    key = key.upper() if upper else key
    return key.replace("_", "-") if dashed else key


@st.composite
def nested_under(draw: st.DrawFn, leaf: tuple[str, object]) -> dict[str, object]:
    """The leaf `{key: value}` placed in dictionaries and lists up to four levels deep."""
    value: object = {leaf[0]: leaf[1]}
    for _ in range(draw(st.integers(min_value=0, max_value=4))):
        value = {draw(plain_keys): [value]} if draw(st.booleans()) else {draw(plain_keys): value}
    return {"payload": value}


@given(data=st.data(), key=sensitive_keys(), secret=secrets)
def test_a_value_under_a_sensitive_key_never_reaches_a_line(
    data: st.DataObject, key: str, secret: str
) -> None:
    fields = data.draw(nested_under((key, secret)))

    with captured_logs() as captured:
        log.info("Событие", **fields)
        log.info("Событие", **{key.replace("-", "_"): secret})

    assert secret not in captured.text()
    assert REDACTED in captured.text()


@given(data=st.data(), key=plain_keys, secret=secrets)
def test_a_secret_string_never_reaches_a_line_under_any_key(
    data: st.DataObject, key: str, secret: str
) -> None:
    fields = data.draw(nested_under((key, SecretStr(secret))))

    with captured_logs() as captured:
        log.info("Событие", **fields)

    assert secret not in captured.text()


@given(key=plain_keys, password=secrets)
def test_a_password_inside_a_url_never_reaches_a_line(key: str, password: str) -> None:
    url = f"postgresql://shosai_app:{password}@db.ru.example:6432/shosai"

    # Адрес внутри самого сообщения: так его пишут, когда текст ошибки собран заранее.
    message = f"Нет соединения с {url}"
    with captured_logs() as captured:
        log.info(message, **{key: url})
        logging.getLogger("psycopg").error("Сбой %s", url)
        try:
            raise ConnectionError(url)
        except ConnectionError:
            log.exception("Сбой подключения")

    assert password not in captured.text()
    assert "postgresql://shosai_app:***@db.ru.example:6432/shosai" in captured.text()


def test_logging_the_settings_reveals_no_secret() -> None:
    settings = load_settings(production_environ())

    with captured_logs() as captured:
        log.info("Настройки прочитаны", settings=settings, crypto=settings.crypto)

    assert SAMPLE_SECRET not in captured.text()
    assert SAMPLE_FERNET_KEY not in captured.text()


def test_token_counters_stay_visible() -> None:
    with captured_logs() as captured:
        log.info("Ответ модели", input_tokens=120, output_tokens=48, tokens=168)

    [line] = captured.lines()
    assert (line["input_tokens"], line["output_tokens"]) == (120, 48)
    assert line["tokens"] == 168


@pytest.mark.parametrize(
    ("key", "sensitive"),
    [
        ("Authorization", True),
        ("X-Api-Key", True),
        ("s3_secret_access_key", True),
        ("refresh_token", True),
        ("Set-Cookie", True),
        ("input_tokens", False),
        ("cache_key", False),
        ("endpoint_url", False),
    ],
)
def test_sensitive_keys(key: str, *, sensitive: bool) -> None:
    assert is_sensitive_key(key) is sensitive


def test_a_structure_deeper_than_the_limit_is_cut() -> None:
    value: object = "zq-deep-secret"
    for _ in range(MAX_DEPTH + 2):
        value = [value]

    redacted = redact_value(value)

    for _ in range(MAX_DEPTH + 1):
        assert isinstance(redacted, list)
        [redacted] = redacted
    assert redacted == TRUNCATED
