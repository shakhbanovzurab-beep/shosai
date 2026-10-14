"""Process roles of the one backend image (target architecture §5)."""

from enum import StrEnum


class ProcessRole(StrEnum):
    """What a process of the backend image runs; the console command names the role.

    The value appears in every log line and in the telemetry resource, so the signals of
    the roles stay apart.
    """

    API = "api"
    WS = "ws"
    WORKERS = "workers"
    SCHEDULER = "scheduler"
    # Разовая команда миграций обоих домов; долгоживущим процессом не является.
    MIGRATE = "migrate"
    # Разовые команды оператора над ИИ: аварийный выключатель (F6-D5).
    AI = "ai"
    # Разовая проверка почты: письмо каждого вида через SMTP.
    EMAIL = "email"
    # Разовые команды оператора над аккаунтами: первая роль владельца.
    IDENTITY = "identity"
