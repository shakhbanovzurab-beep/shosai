"""Where a process listens: loopback by default, two different ports, each in range."""

from ipaddress import IPv4Address, IPv6Address

import pytest

from shosai.core.config.loading import ConfigurationError, load_settings
from tests.core.config.sample_environ import local_environ


def test_by_default_a_process_listens_on_loopback() -> None:
    server = load_settings(local_environ()).server

    assert (server.bind_host, server.http_port, server.ops_port) == (
        IPv4Address("127.0.0.1"),
        8000,
        9100,
    )


def test_a_container_binds_every_address_of_its_own_network() -> None:
    server = load_settings(local_environ(BIND_HOST="::", HTTP_PORT="8080")).server

    assert (server.bind_host, server.http_port) == (IPv6Address("::"), 8080)


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"HTTP_PORT": "9100"}, "ServerSettings: Value error, HTTP_PORT и OPS_PORT совпадают"),
        ({"OPS_PORT": "70000"}, "OPS_PORT: Input should be less than or equal to 65535"),
        ({"BIND_HOST": "localhost"}, "BIND_HOST: value is not a valid IPv4 or IPv6 address"),
    ],
)
def test_a_listening_problem_is_named(overrides: dict[str, str], problem: str) -> None:
    with pytest.raises(ConfigurationError) as raised:
        load_settings(local_environ(**overrides))

    assert raised.value.problems == (problem,)
