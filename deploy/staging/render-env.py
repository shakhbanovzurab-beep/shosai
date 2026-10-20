#!/usr/bin/env python3
"""Render the staging environment files from the owner's `.env` (F4 step 3).

Usage, as root on the staging host:

    python3 deploy/staging/render-env.py /root/shosai/.env /srv/shosai

The owner's file keeps some draft-era names (`SMTP_USER`, `SMTP_TLS_MODE`, the `*_INFO`
mailbox); this script maps them to the settings of `.env.example`, builds the database
addresses with `sslmode=verify-full`, and generates the secrets that only staging uses
(Valkey, the cache, Qdrant, unsubscribe links, the admin sign-in address, Grafana's admin
password). It also writes the observability stack's files (F5 step 10): Alertmanager's bot,
chat and heartbeat address, Grafana's password, the probe targets and the stack's `.env`.
Generated secrets
are kept in `secrets/generated.env` and reused on every later run, so rendering again never
rotates them. No value is ever printed. Every written file is mode 600, owned by `deploy`.
"""

import hashlib
import os
import pwd
import secrets
import string
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

DEPLOY_USER = "deploy"
# Статический адрес Valkey в сети плоскости: гейт пускает redis:// только на IP частной сети.
VALKEY_ADDRESS = "172.30.42.10"
EDGE_ADDRESS = "172.30.42.2"
INTERNAL_CA = "/run/shosai-tls/internal-ca.crt"
TIMEWEB_CA = "/run/shosai-tls/timeweb-ca.crt"
STORAGE_ORIGIN_SCHEME = "https://"
SERVER_NAME = "shosai.tech"
# Модель OpenRouter по умолчанию для заметок встреч, та же, что в .env.example.
NOTES_MODEL = "google/gemini-3.8-flash"
TRANSCRIBE_MODEL = "openai/whisper-large-v3"
DIARIZE_MODEL = "precision-3"
GENERATED = (
    "VALKEY_PASSWORD",
    "REDIS_CACHE_PASSWORD",
    "QDRANT_API_KEY",
    "EMAIL_LINK_SECRET",
    "ADMIN_LOGIN_SEGMENT",
    "GRAFANA_ADMIN_PASSWORD",
)
# Пользователи процессов стека наблюдаемости в их образах: Alertmanager и Prometheus — nobody.
NOBODY = (65534, 65534)
GRAFANA = (472, 0)
OBSERVABILITY_FILES = "compose.yaml:compose.staging.yaml"
# Переменные, которые переходят из файла владельца как есть.
COPIED = (
    "FERNET_KEY",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MANAGEMENT_KEY",
    "PYANNOTE_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_LIVE_API_KEY",
    "MISTRAL_API_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "PUBLIC_BASE_URL",
    "IDENTITY_TOKEN_KEYS",
    "IDENTITY_DIRECTORY_HMAC_KEY",
    "IDENTITY_PASSWORD_HASH_ROUNDS",
    "IDENTITY_TURNSTILE_SITE_KEY",
    "IDENTITY_TURNSTILE_SECRET_KEY",
    "IDENTITY_YANDEX_CLIENT_ID",
    "IDENTITY_YANDEX_CLIENT_SECRET",
    "IDENTITY_VK_CLIENT_ID",
    "IDENTITY_GOOGLE_CLIENT_ID",
    "IDENTITY_GOOGLE_CLIENT_SECRET",
    "IDENTITY_GITHUB_CLIENT_ID",
    "IDENTITY_GITHUB_CLIENT_SECRET",
    "IDENTITY_TRANSFERS_ALLOWED",
    "IDENTITY_ADMIN_USERNAME",
    "IDENTITY_ADMIN_PASSWORD_HASH",
    "NOTES_MODEL",
    "NOTES_FALLBACK_MODEL",
    "NOTES_TRANSCRIBE_MODEL",
    "NOTES_TRANSCRIBE_FALLBACK_MODEL",
    "NOTES_DIARIZE_MODEL",
    *(f"HOME_{home}_S3_{part}" for home in ("RU", "EU")
      for part in ("ENDPOINT_URL", "REGION", "BUCKET", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY")),
)
# Как SMTP_TLS_MODE черновика называется в SMTP_SECURITY.
SMTP_SECURITY = {"ssl": "tls", "tls": "tls", "starttls": "starttls"}
# Переход на имена NOTES_* (ADR 0057): на один релиз пишутся и прежние имена с теми же
# значениями, чтобы прежние образы стартовали после перезагрузки хоста и при
# `release.sh rollback`. Убираются отдельным коммитом, когда новый релиз здоров.
RENAMED_SETTINGS = {
    "NOTES_MODEL": "MEETINGS_NOTES_MODEL",
    "NOTES_FALLBACK_MODEL": "MEETINGS_NOTES_FALLBACK_MODEL",
    "NOTES_TRANSCRIBE_MODEL": "MEETINGS_TRANSCRIBE_MODEL",
    "NOTES_TRANSCRIBE_FALLBACK_MODEL": "MEETINGS_TRANSCRIBE_FALLBACK_MODEL",
    "NOTES_DIARIZE_MODEL": "MEETINGS_DIARIZE_MODEL",
}


def read_env(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines; surrounding single or double quotes are removed."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key[:1].isupper() or line.startswith("#"):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def render(values: dict[str, str]) -> str:
    """One KEY='value' line per entry; values never contain a single quote."""
    lines = []
    for key, value in values.items():
        if "'" in value or "\n" in value:
            message = f"{key}: значение с одинарной кавычкой или переводом строки"
            raise ValueError(message)
        lines.append(f"{key}='{value}'")
    return "\n".join(lines) + "\n"


def write_private(path: Path, text: str, owner: tuple[int, int], mode: int = 0o600) -> None:
    """Write a file readable only by its owner, replacing any earlier one atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.chown(temporary, *owner)
    temporary.chmod(mode)
    temporary.replace(path)


def generated_secrets(path: Path) -> dict[str, str]:
    """Secrets made once for staging and reused on every later run."""
    known = read_env(path) if path.exists() else {}
    alphabet = string.ascii_lowercase + string.digits
    for key in GENERATED:
        if key in known:
            continue
        if key == "ADMIN_LOGIN_SEGMENT":
            known[key] = "staff-" + "".join(secrets.choice(alphabet) for _ in range(12))
        else:
            known[key] = secrets.token_urlsafe(48)
    return known


def database_url(user: str, password: str, host: str, port: str, ca: str) -> str:
    """A libpq address that checks the server's certificate and host name."""
    netloc_host = f"[{host}]" if ":" in host else host
    return (
        f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{netloc_host}:{port}"
        f"/shosai?sslmode=verify-full&sslrootcert={ca}"
    )


def acl(user: str, password: str, rules: str) -> str:
    """A Valkey or Redis ACL file: the default user off, one user with a hashed password."""
    digest = hashlib.sha256(password.encode()).hexdigest()
    return (
        "user default off\n"
        f"user {user} on #{digest} {rules}\n"
        # Проверка здоровья контейнера: только PING, без пароля и без доступа к данным.
        "user healthcheck on nopass -@all +ping\n"
    )


def backend_env(source: dict[str, str], generated: dict[str, str]) -> dict[str, str]:
    """What every long-running backend role reads; the migrator's password is not here."""
    env = {
        "ENVIRONMENT": "staging",
        "LOG_LEVEL": "INFO",
        "API_DOCS_ENABLED": "false",
        "TRUSTED_PROXY_ADDRESSES": EDGE_ADDRESS,
        "IDENTITY_COOKIE_SECURE": "true",
        "EMAIL_SENDER_NAME": "Shosai",
        "SMTP_SECURITY": SMTP_SECURITY[source["SMTP_TLS_MODE"].lower()],
        "SMTP_ACCOUNT_USER": source["SMTP_USER"],
        "SMTP_ACCOUNT_PASSWORD": source["SMTP_PASSWORD"],
        "SMTP_NOTIFICATIONS_USER": source["SMTP_USER_INFO"],
        "SMTP_NOTIFICATIONS_PASSWORD": source["SMTP_PASSWORD_INFO"],
        "EMAIL_LINK_SECRET": generated["EMAIL_LINK_SECRET"],
        "VALKEY_URL": f"redis://shosai:{quote(generated['VALKEY_PASSWORD'], safe='')}"
        f"@{VALKEY_ADDRESS}:6379/0",
        "REDIS_CACHE_URL": "redis://shosai:"
        f"{quote(generated['REDIS_CACHE_PASSWORD'], safe='')}@redis-cache:6379/0",
        "QDRANT_URL": "http://qdrant:6333",
        "QDRANT_API_KEY": generated["QDRANT_API_KEY"],
        # Трейсы ролей — в коллектор стека наблюдаемости (F5); оповещения о бизнес-событиях — в его
        # Alertmanager (ADR 0052).
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318",
        "ALERTING_ENABLED": "true",
        # Скачивания идут через edge, который ставит nosniff и песочницу (FL-D9, ADR 0055 п. 8).
        "FILES_DOWNLOAD_BASE_URL": f"https://{SERVER_NAME}/dl",
        # Модель заметок встреч до studio (notes шаг 6); владелец может задать свою в .env.
        "NOTES_MODEL": NOTES_MODEL,
        "NOTES_TRANSCRIBE_MODEL": TRANSCRIBE_MODEL,
        "NOTES_DIARIZE_MODEL": DIARIZE_MODEL,
    }
    env |= {key: source[key] for key in COPIED if source.get(key)}
    for home in ("RU", "EU"):
        env[f"HOME_{home}_DATABASE_URL"] = database_url(
            source[f"HOME_{home}_APP_USER"], source[f"HOME_{home}_APP_PASSWORD"],
            f"pgbouncer-{home.lower()}", "6432", INTERNAL_CA,
        )  # fmt: skip
    env |= {former: env[current] for current, former in RENAMED_SETTINGS.items() if current in env}
    return env


def storage_origin(endpoint: str) -> str:
    """The bucket's scheme://host[:port], as the edge's downloads reach it; only over TLS."""
    parts = urlsplit(endpoint)
    if parts.scheme != "https" or not parts.netloc:
        sys.exit(f"хранилище дома не по HTTPS: {parts.scheme}://{parts.netloc}")
    return f"{parts.scheme}://{parts.netloc}"


def probe_targets(source: dict[str, str], domain: str) -> str:
    """Prometheus file_sd targets: health through the edge and each home's database."""
    lines = [
        "# Пробы staging (render-env.py): здоровье через edge и TCP к базе дома.",
        f'- targets: ["https://{domain}/v1/health"]',
        "  labels: {module: https_health, probe: edge_health}",
    ]
    for home in ("RU", "EU"):
        host = source[f"HOME_{home}_DATABASE_HOST"]
        port = source.get(f"HOME_{home}_DATABASE_PORT", "5432")
        address = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
        lines += [
            f'- targets: ["{address}"]',
            f"  labels: {{module: tcp_connect, probe: home_database, home: {home.lower()}}}",
        ]
    return "\n".join(lines) + "\n"


def write_observability(source: dict[str, str], generated: dict[str, str], target: Path,
                        owner: tuple[int, int]) -> None:  # fmt: skip
    """The stack's secrets, probe targets and `.env`; nothing is written without its source."""
    alertmanager = target / "secrets" / "alertmanager"
    alertmanager.mkdir(parents=True, exist_ok=True)
    for name, key in (
        ("telegram-bot-token", "MONITORING_TELEGRAM_BOT_TOKEN"),
        ("telegram-chat-id", "MONITORING_TELEGRAM_CHAT_ID"),
        ("heartbeat-url", "HEARTBEAT_PING_URL"),
    ):
        if source.get(key):
            # Без перевода строки: Alertmanager читает файл целиком (как alertmanager-secrets.sh).
            write_private(alertmanager / name, source[key], NOBODY)
    alertmanager.chmod(0o700)
    os.chown(alertmanager, *NOBODY)
    grafana = target / "secrets" / "grafana"
    write_private(grafana / "admin-password", generated["GRAFANA_ADMIN_PASSWORD"], GRAFANA)
    grafana.chmod(0o700)
    os.chown(grafana, *GRAFANA)
    write_private(target / "telemetry" / "probe-targets" / "probes.yml",
                  probe_targets(source, "shosai.tech"), NOBODY, 0o644)  # fmt: skip
    stack = target / "observability" / ".env"
    images = read_env(stack) if stack.exists() else {}
    write_private(stack, render({
        "COMPOSE_FILE": OBSERVABILITY_FILES,
        "SHOSAI_OBSERVABILITY_IMAGE": images.get(
            "SHOSAI_OBSERVABILITY_IMAGE", "shosai-observability:staging"
        ),
    }), owner)  # fmt: skip


def main(source_path: Path, target: Path) -> None:
    """Render every staging file under `target`."""
    source = read_env(source_path)
    account = pwd.getpwnam(DEPLOY_USER)
    owner = (account.pw_uid, account.pw_gid)
    generated_path = target / "secrets" / "generated.env"
    generated = generated_secrets(generated_path)
    write_private(generated_path, render(generated), owner)
    write_private(target / ".env.staging", render(backend_env(source, generated)), owner)
    migrate = {
        f"HOME_{home}_MIGRATION_DATABASE_URL": database_url(
            source[f"HOME_{home}_MIGRATOR_USER"], source[f"HOME_{home}_MIGRATOR_PASSWORD"],
            source[f"HOME_{home}_DATABASE_HOST"], source.get(f"HOME_{home}_DATABASE_PORT", "5432"),
            TIMEWEB_CA,
        )
        for home in ("RU", "EU")
    }  # fmt: skip
    write_private(target / "secrets" / "migrate.env", render(migrate), owner)
    for home in ("RU", "EU"):
        pool = {
            "PGBOUNCER_APP_USER": source[f"HOME_{home}_APP_USER"],
            "PGBOUNCER_APP_PASSWORD": source[f"HOME_{home}_APP_PASSWORD"],
            "PGBOUNCER_SERVER_HOST": source[f"HOME_{home}_DATABASE_HOST"],
            "PGBOUNCER_SERVER_DATABASE": source.get(f"HOME_{home}_DATABASE_NAME", "shosai"),
        }
        write_private(target / "secrets" / f"pgbouncer-{home.lower()}.env", render(pool), owner)
    write_private(
        target / "secrets" / "qdrant.env",
        render({"QDRANT__SERVICE__API_KEY": generated["QDRANT_API_KEY"]}),
        owner,
    )
    # Файлы ACL читают процессы Valkey (uid 999) и Redis (uid 999): пароли в них — хеши.
    for name, key, rules in (
        ("valkey", "VALKEY_PASSWORD", "~* &* +@all"),
        ("redis-cache", "REDIS_CACHE_PASSWORD", "~* &* +@all"),
    ):
        write_private(target / "secrets" / f"{name}.acl", acl("shosai", generated[key], rules),
                      (999, 999))  # fmt: skip
    write_private(
        target / "secrets" / "cabinet.env",
        render({
            "VITE_TURNSTILE_SITE_KEY": source["IDENTITY_TURNSTILE_SITE_KEY"],
            "VITE_GTM_CONTAINER_ID": "GTM-MLQW5VGQ",
            "VITE_ADMIN_LOGIN_PATH": "/admin/" + generated["ADMIN_LOGIN_SEGMENT"],
        }),
        owner,
    )  # fmt: skip
    # Не секреты: адреса для edge и Compose. Образы задаёт release (шаг 4) или человек.
    origins = sorted({
        source[f"HOME_{home}_S3_ENDPOINT_URL"].rstrip("/") for home in ("RU", "EU")
        if source[f"HOME_{home}_S3_ENDPOINT_URL"].startswith(STORAGE_ORIGIN_SCHEME)
    })  # fmt: skip
    downloads = {
        f"SHOSAI_DOWNLOAD_{home}_ORIGIN": storage_origin(source[f"HOME_{home}_S3_ENDPOINT_URL"])
        for home in ("RU", "EU")
    }
    compose = target / ".env"
    images = read_env(compose) if compose.exists() else {}
    write_private(
        compose,
        render({
            "SHOSAI_BACKEND_IMAGE": images.get("SHOSAI_BACKEND_IMAGE", "shosai-backend:staging"),
            "SHOSAI_EDGE_IMAGE": images.get("SHOSAI_EDGE_IMAGE", "shosai-edge:staging"),
            "SHOSAI_SERVER_NAME": SERVER_NAME,
            "SHOSAI_CSP_STORAGE_ORIGINS": " ".join(origins),
            **downloads,
        }),
        owner,
    )  # fmt: skip
    write_observability(source, generated, target, owner)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: render-env.py <owner .env> <staging directory>")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
