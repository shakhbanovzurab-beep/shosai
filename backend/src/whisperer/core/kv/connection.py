"""Clients of the Redis-protocol servers of a process: Valkey and the LRU cache (§4.2).

One client with one bounded connection pool per server per process. Every call waits at
most its own deadline (`asyncio.timeout` at the call site), so the client never retries
by itself: a retried `SET NX` or rate-limit script could apply twice, and the caller
decides what a failure means — fail open, fail closed or a cache miss. redis-py drops a
connection whose reply was interrupted by a deadline, so no half-read reply returns to the
pool. A connection idle longer than the health-check interval is pinged before use: a
managed server closes idle connections, and the first call after a quiet spell would
otherwise fail on a dead socket (draft lesson).
"""

from typing import Final

from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from pydantic import SecretStr
from redis.asyncio import BlockingConnectionPool, Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

# Предел запросов в работе у процесса API (§4.3): каждому хватает соединения без ожидания.
# Соединения открываются по требованию, поэтому запас ничего не стоит, пока не нужен.
MAX_CONNECTIONS: Final = 64
# Ожидание свободного соединения у вызова без своего дедлайна; вызов с дедлайном
# прерывается раньше.
POOL_WAIT_SECONDS: Final = 2
CONNECT_TIMEOUT_SECONDS: Final = 2
# Страховка для вызовов без дедлайна; блокирующие чтения потоков задач короче (≤ 2 с).
SOCKET_TIMEOUT_SECONDS: Final = 5
HEALTH_CHECK_INTERVAL_SECONDS: Final = 30
# Сбой связи, дедлайн вызова и отказ сервера (например, OOM при noeviction) значат одно:
# сервер не ответил вовремя. Что из этого следует, решает вызывающий.
REDIS_FAILURES: Final = (RedisError, TimeoutError, OSError)


def connect_redis(
    url: SecretStr, client_name: str, tracer_provider: TracerProvider | None = None
) -> Redis:
    """A client over a bounded pool; connections open on first use, not here.

    `client_name` shows the process role in `CLIENT LIST` of the server. With a tracer
    provider every command becomes a client span with its arguments replaced by `?`.
    """
    pool = BlockingConnectionPool.from_url(
        url.get_secret_value(),
        max_connections=MAX_CONNECTIONS,
        timeout=POOL_WAIT_SECONDS,
        socket_connect_timeout=CONNECT_TIMEOUT_SECONDS,
        socket_timeout=SOCKET_TIMEOUT_SECONDS,
        socket_keepalive=True,
        health_check_interval=HEALTH_CHECK_INTERVAL_SECONDS,
        retry=Retry(NoBackoff(), 0),
        client_name=client_name,
    )
    client = Redis.from_pool(pool)
    if tracer_provider is not None:
        RedisInstrumentor.instrument_client(client, tracer_provider=tracer_provider)
    return client
