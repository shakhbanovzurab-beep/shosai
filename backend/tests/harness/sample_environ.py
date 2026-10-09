"""An environment with TEST_* variables for the harness unit tests; it never connects."""

from shosai.core.kernel.homes import Home

SAMPLE_PASSWORD = "sample-secret-value"


def sample_url(user: str, port: int, *, host: str = "127.0.0.1", database: str = "") -> str:
    """A test database URL in the application's format."""
    name = database or "shosai_test"
    return f"postgresql://{user}:{SAMPLE_PASSWORD}@{host}:{port}/{name}"


def sample_environ(**overrides: str) -> dict[str, str]:
    """A full TEST_* set with F3's local ports; `overrides` replaces or adds variables."""
    ports = {Home.RU: (16432, 15432), Home.EU: (16433, 15433)}
    environ = {
        "TEST_DATABASE_SLOTS": "8",
        "TEST_VALKEY_URL": f"redis://:{SAMPLE_PASSWORD}@127.0.0.1:16379",
        "TEST_REDIS_CACHE_URL": f"redis://:{SAMPLE_PASSWORD}@127.0.0.1:16380",
        "TEST_S3_ENDPOINT_URL": "http://127.0.0.1:18333",
        "TEST_S3_REGION": "local",
        "TEST_S3_BUCKET": "shosai",
        "TEST_S3_ACCESS_KEY_ID": "local-s3-access",
        "TEST_S3_SECRET_ACCESS_KEY": SAMPLE_PASSWORD,
    }
    for home, (application_port, migration_port) in ports.items():
        environ[f"TEST_HOME_{home.name}_DATABASE_URL"] = sample_url("shosai_app", application_port)
        environ[f"TEST_HOME_{home.name}_MIGRATION_DATABASE_URL"] = sample_url(
            "shosai_migrator", migration_port
        )
    environ.update(overrides)
    return environ
