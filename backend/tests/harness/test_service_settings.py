"""Valkey, the cache and the bucket of the tests come only from TEST_* and stay on loopback."""

import pytest

from tests.harness.guards import UnsafeTestTargetError, ensure_safe_targets
from tests.harness.sample_environ import SAMPLE_PASSWORD, sample_environ
from tests.harness.settings import HarnessConfigurationError, HarnessSettings

SERVICE_VARIABLES = [
    "TEST_VALKEY_URL",
    "TEST_REDIS_CACHE_URL",
    "TEST_S3_ENDPOINT_URL",
    "TEST_S3_REGION",
    "TEST_S3_BUCKET",
    "TEST_S3_ACCESS_KEY_ID",
    "TEST_S3_SECRET_ACCESS_KEY",
]


def check(environ: dict[str, str]) -> None:
    ensure_safe_targets(HarnessSettings.from_environ(environ), environ)


def test_the_slot_number_is_the_database_index() -> None:
    services = HarnessSettings.from_environ(sample_environ()).services

    assert services.valkey.for_slot(3).get_secret_value() == (
        f"redis://:{SAMPLE_PASSWORD}@127.0.0.1:16379/3"
    )
    assert services.cache.for_slot(15).get_secret_value().endswith("@127.0.0.1:16380/15")
    assert services.storage.s3_bucket == "shosai"


def test_every_service_variable_is_required_and_runtime_ones_are_never_read() -> None:
    environ = sample_environ()
    for variable in SERVICE_VARIABLES:
        del environ[variable]
    environ |= {
        "VALKEY_URL": f"redis://:{SAMPLE_PASSWORD}@127.0.0.1:16379/0",
        "S3_BUCKET": "shosai",
    }

    with pytest.raises(HarnessConfigurationError) as raised:
        HarnessSettings.from_environ(environ)

    message = str(raised.value)
    for variable in SERVICE_VARIABLES:
        assert f"{variable}: не задана" in message
    assert SAMPLE_PASSWORD not in message


@pytest.mark.parametrize(
    "url",
    [
        f"redis://:{SAMPLE_PASSWORD}@127.0.0.1:16379/0",
        f"redis://:{SAMPLE_PASSWORD}@127.0.0.1:16379/2",
        f"redis://:{SAMPLE_PASSWORD}@127.0.0.1:16379?db=2",
        f"http://:{SAMPLE_PASSWORD}@127.0.0.1:16379",
    ],
)
def test_a_redis_address_carries_no_database_index(url: str) -> None:
    with pytest.raises(HarnessConfigurationError, match="TEST_VALKEY_URL: ") as raised:
        HarnessSettings.from_environ(sample_environ(TEST_VALKEY_URL=url))

    assert SAMPLE_PASSWORD not in str(raised.value)


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("TEST_VALKEY_URL", f"redis://:{SAMPLE_PASSWORD}@valkey.eu.example:6379"),
        ("TEST_REDIS_CACHE_URL", f"rediss://:{SAMPLE_PASSWORD}@10.0.0.7:6379"),
        ("TEST_S3_ENDPOINT_URL", "https://s3.ru.example"),
    ],
)
def test_refuses_a_service_that_is_not_on_loopback(variable: str, value: str) -> None:
    with pytest.raises(UnsafeTestTargetError, match=f"{variable}: хост .* не петлевой"):
        check(sample_environ(**{variable: value}))


def test_accepts_the_development_bucket_endpoint() -> None:
    environ = sample_environ()
    environ["S3_ENDPOINT_URL"] = environ["TEST_S3_ENDPOINT_URL"]

    check(environ)


def test_refuses_valkey_equal_to_the_runtime_address() -> None:
    environ = sample_environ()
    environ["VALKEY_URL"] = environ["TEST_VALKEY_URL"]

    with pytest.raises(UnsafeTestTargetError, match="TEST_VALKEY_URL: совпадает"):
        check(environ)


def test_reads_an_ipv6_loopback_endpoint() -> None:
    check(sample_environ(TEST_S3_ENDPOINT_URL="http://[::1]:18333"))
