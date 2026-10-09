"""The harness's direct connections to the test databases and its SQL files."""

import socket
from functools import cache
from pathlib import Path
from typing import Final

import psycopg
from psycopg import sql
from psycopg.rows import DictRow, dict_row

from tests.harness.settings import DatabaseTarget, HarnessConfigurationError

type Connection = psycopg.AsyncConnection[DictRow]
type QueryParams = tuple[object, ...]

CONNECT_TIMEOUT_SECONDS: Final = 5
APPLICATION_NAME: Final = "shosai-tests"
SQL_DIRECTORY: Final = Path(__file__).parent
MAINTENANCE_DATABASE: Final = "postgres"
DATABASE_EXISTS_SQL: Final = "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = %s)"


async def connect(target: DatabaseTarget) -> Connection:
    """Open an autocommit connection without server-side prepared statements (ADR 0013)."""
    try:
        return await _open(target, target.database)
    except psycopg.OperationalError:
        # SQLSTATE при отказе в подключении psycopg не сообщает: отсутствие базы слота
        # проверяется по каталогу сервера через служебную базу.
        if await _database_exists(target) is False:
            message = (
                f"{target.variable}: на {target.host}:{target.port} нет базы {target.database}; "
                "TEST_DATABASE_SLOTS больше числа подготовленных баз (LOCAL_TEST_DATABASE_COUNT)"
            )
            raise HarnessConfigurationError(message) from None
        raise


async def _open(target: DatabaseTarget, database: str) -> Connection:
    return await psycopg.AsyncConnection.connect(
        host=target.host,
        port=target.port,
        user=target.user,
        password=target.password,
        dbname=database,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        application_name=APPLICATION_NAME,
        autocommit=True,
        prepare_threshold=None,
        row_factory=dict_row,
    )


async def _database_exists(target: DatabaseTarget) -> bool | None:
    """Whether the server has the database; None when the server cannot be asked either."""
    try:
        connection = await _open(target, MAINTENANCE_DATABASE)
    except psycopg.OperationalError:
        return None
    try:
        exists = await fetch_value(connection, DATABASE_EXISTS_SQL, (target.database,))
    finally:
        await connection.close()
    return exists is True


async def fetch_rows(
    connection: Connection, query: str | sql.Composed, params: QueryParams = ()
) -> list[DictRow]:
    """All rows of a query; with no params `%` in the query is taken literally."""
    cursor = await connection.execute(_query(query), params or None)
    return await cursor.fetchall()


async def fetch_value(
    connection: Connection, query: str | sql.Composed, params: QueryParams = ()
) -> object:
    """The first column of the first row, or None when the query returns no rows."""
    cursor = await connection.execute(_query(query), params or None)
    row = await cursor.fetchone()
    return None if row is None else next(iter(row.values()))


def drop_without_goodbye(connection: Connection) -> None:
    """Cut the socket the way a crashed process does: no protocol Terminate message."""
    duplicate = socket.socket(fileno=connection.pgconn.socket)
    try:
        duplicate.shutdown(socket.SHUT_RDWR)
    finally:
        # Дескриптор принадлежит libpq: отвязываем его от объекта сокета, не закрывая.
        duplicate.detach()


@cache
def load_sql(name: str) -> str:
    """Text of a harness SQL file, read once per run."""
    return (SQL_DIRECTORY / name).read_text(encoding="utf-8")


def _query(query: str | sql.Composed) -> bytes | sql.Composed:
    # Текст харнесса — доверенный SQL из его файлов и констант; psycopg принимает его байтами.
    return query.encode() if isinstance(query, str) else query
