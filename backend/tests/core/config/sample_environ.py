"""Environments for the settings tests: local values like `.env.example` section 2."""

from cryptography.fernet import Fernet

from shosai.core.kernel.homes import Home

SAMPLE_SECRET = "sample-secret-value"
SAMPLE_FERNET_KEY = Fernet.generate_key().decode()
SAMPLE_LINK_SECRET = "sample-link-secret-at-least-32-characters"
# Ключи identity: разработки — для local_environ, «настоящие» — для production_environ.
SAMPLE_SIGNING_KEY = "sample-signing-key-at-least-32-bytes-long"
# bcrypt стоимости 4 от «sample admin password»: форма хэша, а не настоящий пароль.
SAMPLE_ADMIN_PASSWORD_HASH = "$2b$04$PjpmDhkbnOxT8BsaEzFPUuxiyzztdBZIXBnoFC.wZbSoxprAlyyhi"
DEVELOPMENT_IDENTITY = {
    "IDENTITY_TOKEN_KEYS": f"dev:{SAMPLE_SIGNING_KEY}",
    "IDENTITY_DIRECTORY_HMAC_KEY": "dev-sample-directory-key-at-least-32-bytes",
}
PRODUCTION_IDENTITY = {
    "IDENTITY_TOKEN_KEYS": f"k1:{SAMPLE_SIGNING_KEY}",
    "IDENTITY_DIRECTORY_HMAC_KEY": "sample-directory-key-at-least-32-bytes-long",
    "IDENTITY_TURNSTILE_SITE_KEY": "sample-site-key",
    "IDENTITY_TURNSTILE_SECRET_KEY": SAMPLE_SECRET,
    "IDENTITY_ADMIN_USERNAME": "admin",
    "IDENTITY_ADMIN_PASSWORD_HASH": SAMPLE_ADMIN_PASSWORD_HASH,
}
REQUIRED_VARIABLES = (
    "ENVIRONMENT",
    *(f"HOME_{home.name}_DATABASE_URL" for home in Home),
    *(
        f"HOME_{home.name}_{name}"
        for home in Home
        for name in (
            "S3_ENDPOINT_URL",
            "S3_REGION",
            "S3_BUCKET",
            "S3_ACCESS_KEY_ID",
            "S3_SECRET_ACCESS_KEY",
        )
    ),
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
        **DEVELOPMENT_IDENTITY,
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
            f"{prefix}S3_ENDPOINT_URL": "http://127.0.0.1:18333",
            f"{prefix}S3_REGION": "local",
            f"{prefix}S3_BUCKET": f"shosai-{home.value}",
            f"{prefix}S3_ACCESS_KEY_ID": "local-s3-access",
            f"{prefix}S3_SECRET_ACCESS_KEY": SAMPLE_SECRET,
        }
    environ.update(overrides)
    return environ


def production_environ(**overrides: str) -> dict[str, str]:
    """A production environment that passes the gate; `overrides` replaces or adds variables."""
    environ = local_environ(
        ENVIRONMENT="production",
        HOME_RU_S3_ENDPOINT_URL="https://s3.ru.example",
        HOME_EU_S3_ENDPOINT_URL="https://s3.eu.example",
        VALKEY_URL=f"rediss://:{SAMPLE_SECRET}@valkey.eu.example:6380/0",
        TRUSTED_PROXY_ADDRESSES="10.0.0.0/24",
        FERNET_KEY=SAMPLE_FERNET_KEY,
        OPENROUTER_API_KEY=SAMPLE_SECRET,
        OPENAI_API_KEY=SAMPLE_SECRET,
        GOOGLE_LIVE_API_KEY=SAMPLE_SECRET,
        MISTRAL_API_KEY=SAMPLE_SECRET,
        SMTP_SECURITY="tls",
        SMTP_ACCOUNT_USER="account@shosai.example",
        SMTP_ACCOUNT_PASSWORD=SAMPLE_SECRET,
        SMTP_NOTIFICATIONS_USER="info@shosai.example",
        SMTP_NOTIFICATIONS_PASSWORD=SAMPLE_SECRET,
        EMAIL_LINK_SECRET=SAMPLE_LINK_SECRET,
        FILES_DOWNLOAD_BASE_URL="https://shosai.example/dl",
        NOTES_MODEL="probe/notes",
        AGENT_STANDARD_MODEL="probe/leo",
        AGENT_UTILITY_MODEL="probe/leo-utility",
        NOTES_TRANSCRIBE_MODEL="probe/transcribe",
        **PRODUCTION_IDENTITY,
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
