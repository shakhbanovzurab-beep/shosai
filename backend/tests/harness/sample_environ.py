"""An environment with TEST_* variables for the harness unit tests; it never connects."""

from whisperer.core.kernel.homes import Home

SAMPLE_PASSWORD = "sample-secret-value"


def sample_url(user: str, port: int, *, host: str = "127.0.0.1", database: str = "") -> str:
    """A test database URL in the application's format."""
    name = database or "whisperer_test"
    return f"postgresql+asyncpg://{user}:{SAMPLE_PASSWORD}@{host}:{port}/{name}"


def sample_environ(**overrides: str) -> dict[str, str]:
    """A full TEST_* set with F3's local ports; `overrides` replaces or adds variables."""
    ports = {Home.RU: (16432, 15432), Home.EU: (16433, 15433)}
    environ = {"TEST_DATABASE_SLOTS": "8"}
    for home, (application_port, migration_port) in ports.items():
        environ[f"TEST_HOME_{home.name}_DATABASE_URL"] = sample_url(
            "whisperer_app", application_port
        )
        environ[f"TEST_HOME_{home.name}_MIGRATION_DATABASE_URL"] = sample_url(
            "whisperer_migrator", migration_port
        )
    environ.update(overrides)
    return environ
