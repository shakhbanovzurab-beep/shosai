"""The runtime variables of a backend process over the run's slot (ADR 0009).

A test that starts a role — in this process or as a subprocess — gives it exactly these
variables: the slot's database in each home, the slot's database of Valkey and of the
cache, the test bucket and loopback ports nothing listens on. The run's own environment
never reaches the process, so it can meet no runtime address.
"""

import socket

from shosai.core.kernel.homes import Home
from tests.harness.run_slot import RunSlot
from tests.harness.settings import HarnessSettings

LOOPBACK = "127.0.0.1"


def free_port() -> int:
    """A loopback port nothing listens on now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK, 0))
        return int(probe.getsockname()[1])


def slot_environ(run_slot: RunSlot, settings: HarnessSettings, **overrides: str) -> dict[str, str]:
    """A development process over the slot; `overrides` replaces or adds variables."""
    slot = run_slot.claimed.number
    services = settings.services
    environ = {
        "ENVIRONMENT": "development",
        "BIND_HOST": LOOPBACK,
        "HTTP_PORT": str(free_port()),
        "OPS_PORT": str(free_port()),
        "VALKEY_URL": services.valkey.for_slot(slot).get_secret_value(),
        "REDIS_CACHE_URL": services.cache.for_slot(slot).get_secret_value(),
        # Ключи identity разработки; дешёвый bcrypt ради скорости тестов.
        "IDENTITY_TOKEN_KEYS": "dev:development-signing-key-for-tests-only",
        "IDENTITY_DIRECTORY_HMAC_KEY": "dev-directory-hmac-key-for-tests-only-0000",
        "IDENTITY_PASSWORD_HASH_ROUNDS": "4",
    }
    for home in Home:
        targets = run_slot.claimed.targets(home)
        prefix = f"HOME_{home.name}_"
        environ[f"{prefix}DATABASE_URL"] = targets.application.url().get_secret_value()
        environ[f"{prefix}MIGRATION_DATABASE_URL"] = targets.migration.url().get_secret_value()
        storage = services.storage[home]
        environ |= {
            f"{prefix}S3_ENDPOINT_URL": str(storage.s3_endpoint_url),
            f"{prefix}S3_REGION": storage.s3_region,
            f"{prefix}S3_BUCKET": storage.s3_bucket,
            f"{prefix}S3_ACCESS_KEY_ID": storage.s3_access_key_id,
            f"{prefix}S3_SECRET_ACCESS_KEY": storage.s3_secret_access_key.get_secret_value(),
        }
    environ.update(overrides)
    return environ


def loopback_socket(port: int, path: str) -> str:
    """The address of a WebSocket route of a test server on the loopback."""
    # Semgrep требует wss: тестовый сервер на loopback без TLS, адрес не покидает машину.
    return f"ws://{LOOPBACK}:{port}{path}"  # nosemgrep
