"""Environments for the settings tests: local values like `.env.example` section 2."""

from cryptography.fernet import Fernet

from shosai.core.kernel.homes import Home

SAMPLE_SECRET = "sample-secret-value"
SAMPLE_FERNET_KEY = Fernet.generate_key().decode()
REQUIRED_VARIABLES = (
    "ENVIRONMENT",
    *(f"HOME_{home.name}_DATABASE_URL" for home in Home),
    "S3_ENDPOINT_URL",
    "S3_REGION",
    "S3_BUCKET",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "VALKEY_URL",
    "REDIS_CACHE_URL",
)


def local_environ(**overrides: str) -> dict[str, str]:
    """A complete development environment; `overrides` replaces or adds variables."""
    ports = {Home.RU: (16432, 15432), Home.EU: (16433, 15433)}
    environ = {
        "ENVIRONMENT": "development",
        "VALKEY_URL": f"redis://:{SAMPLE_SECRET}@127.0.0.1:16379/0",
        "REDIS_CACHE_URL": f"redis://:{SAMPLE_SECRET}@127.0.0.1:16380/0",
        "S3_ENDPOINT_URL": "http://127.0.0.1:18333",
        "S3_REGION": "local",
        "S3_BUCKET": "shosai",
        "S3_ACCESS_KEY_ID": "local-s3-access",
        "S3_SECRET_ACCESS_KEY": SAMPLE_SECRET,
    }
    for home, (application_port, migration_port) in ports.items():
        prefix = f"HOME_{home.name}_"
        environ |= {
            f"{prefix}DATABASE_URL": (
                f"postgresql://shosai_app:{SAMPLE_SECRET}@127.0.0.1:{application_port}/shosai"
            ),
            f"{prefix}MIGRATION_DATABASE_URL": (
                f"postgresql://shosai_migrator:{SAMPLE_SECRET}@127.0.0.1:{migration_port}/shosai"
            ),
        }
    environ.update(overrides)
    return environ


def production_environ(**overrides: str) -> dict[str, str]:
    """A production environment that passes the gate; `overrides` replaces or adds variables."""
    environ = local_environ(
        ENVIRONMENT="production",
        S3_ENDPOINT_URL="https://s3.ru.example",
        VALKEY_URL=f"rediss://:{SAMPLE_SECRET}@valkey.eu.example:6380/0",
        TRUSTED_PROXY_ADDRESSES="10.0.0.0/24",
        FERNET_KEY=SAMPLE_FERNET_KEY,
        OPENROUTER_API_KEY=SAMPLE_SECRET,
        PYANNOTE_API_KEY=SAMPLE_SECRET,
    )
    for home in Home:
        del environ[f"HOME_{home.name}_MIGRATION_DATABASE_URL"]
        environ[f"HOME_{home.name}_DATABASE_URL"] = production_database_url(home)
    environ.update(overrides)
    return environ


def production_database_url(home: Home, *, role: str = "shosai_app") -> str:
    """A production-like address of a home's database: TLS with certificate and host checks."""
    return (
        f"postgresql://{role}:{SAMPLE_SECRET}@db.{home.value}.example:6432/shosai"
        "?sslmode=verify-full&sslrootcert=system"
    )
