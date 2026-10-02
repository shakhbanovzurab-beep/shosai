"""Guards against a database that is not a test database (ADR 0009, item 2).

They run before the first write. Messages name the variable and the host, never the
whole URL: it contains the password.
"""

from collections.abc import Mapping
from ipaddress import ip_address

from tests.harness.settings import TEST_DATABASE_NAME, DatabaseTarget, HarnessSettings

TEST_VARIABLE_PREFIX = "TEST_"
RUNTIME_URL_SUFFIX = "_URL"
# Комментарий ставит только init-скрипт F3 (deploy/local/postgres/init-home.sh).
PREPARED_DATABASE_COMMENT_PREFIX = "Prepared test database"
LOOPBACK_HOSTNAME = "localhost"


class UnsafeTestTargetError(Exception):
    """A test target may not be a test database; the run stops before writing."""


def ensure_safe_targets(settings: HarnessSettings, environ: Mapping[str, str]) -> None:
    """Check hosts, database names and equality with runtime URLs; report every problem at once."""
    targets = [
        target
        for home_targets in settings.homes.values()
        for target in (home_targets.application, home_targets.migration)
    ]
    problems = [
        *(problem for target in targets for problem in _target_problems(target)),
        *_runtime_url_problems(settings.database_variables(), environ),
    ]
    if problems:
        raise UnsafeTestTargetError("\n".join(problems))


def ensure_prepared_test_database(target: DatabaseTarget, comment: str | None) -> None:
    """The claimed database is a prepared test database: only F3 marks it so."""
    if comment is None or not comment.startswith(PREPARED_DATABASE_COMMENT_PREFIX):
        message = (
            f"{target.variable}: база {target.database} на {target.host}:{target.port} "
            f"не помечена как подготовленная тестовая ('{PREPARED_DATABASE_COMMENT_PREFIX} …')"
        )
        raise UnsafeTestTargetError(message)


def is_loopback(host: str) -> bool:
    """The host is a loopback address: the name localhost or an IP in 127.0.0.0/8 or ::1."""
    if host == LOOPBACK_HOSTNAME:
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _target_problems(target: DatabaseTarget) -> list[str]:
    problems: list[str] = []
    if not is_loopback(target.host):
        problems.append(f"{target.variable}: хост {target.host} не петлевой адрес")
    if target.database != TEST_DATABASE_NAME:
        problems.append(
            f"{target.variable}: имя базы {target.database}, ожидается {TEST_DATABASE_NAME}"
        )
    return problems


def _runtime_url_problems(test_variables: tuple[str, ...], environ: Mapping[str, str]) -> list[str]:
    runtime_urls = {
        value
        for name, value in environ.items()
        if not name.startswith(TEST_VARIABLE_PREFIX) and name.endswith(RUNTIME_URL_SUFFIX)
    }
    return [
        f"{variable}: совпадает с рабочим адресом из окружения"
        for variable in test_variables
        if environ.get(variable) in runtime_urls
    ]
