"""The admin's routes over the identity bench: the session, accounts, and transfers kept closed."""

import httpx
from fastapi import APIRouter
from pydantic import SecretStr
from redis.asyncio import Redis

from shosai.core.ai.spend.reports import SpendReports
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.kv.rate_limits import RateLimiter
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.application.account_states import AccountStates
from shosai.features.identity.application.admin_access import AdminAccess, AdminCredentials
from shosai.features.identity.application.admin_users import AdminUsers
from shosai.features.identity.application.transfers import Transfers
from shosai.features.identity.channels.http.admin_session import build_admin_session_router
from shosai.features.identity.channels.http.admin_transfers import build_admin_transfers_router
from shosai.features.identity.channels.http.admin_users import build_admin_users_router
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.admin_sessions import AdminSessions
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from tests.features.identity.passwordless_bench import COOKIES, SIGNING_KEYS

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "a long admin passphrase"


async def admin_access(valkey: Redis, hasher: PasswordHasher, limiter: RateLimiter) -> AdminAccess:
    """The admin of the bench, with its password hashed at the bench's cost."""
    credentials = AdminCredentials(ADMIN_USERNAME, SecretStr(await hasher.hash(ADMIN_PASSWORD)))
    signing = SIGNING_KEYS[0].secret.get_secret_value().encode()
    return AdminAccess(credentials, hasher, AdminSessions(valkey, signing), limiter)


def admin_routers(
    transactions: HomeTransactions,
    directory: tuple[Directory, bytes],
    events: tuple[AccountMarkers, EventOutbox],
    access: tuple[AdminAccess, RateLimiter, PortDirectory],
) -> tuple[APIRouter, ...]:
    """`/v1/admin/session`, `/v1/admin/users*` and the transfer routes over the slot's homes."""
    markers, outbox = events
    admin, limiter, ports = access
    users = AdminUsers(transactions, directory, SpendReports(transactions))
    states = AccountStates(transactions, directory[0], markers, outbox)
    transfers = Transfers(transactions, directory[0], outbox, allowed=False)
    return (
        build_admin_session_router(admin, ports, limiter, COOKIES),
        build_admin_users_router(users, states, ports),
        build_admin_transfers_router(transfers, ports),
    )


async def sign_in_admin(http: httpx.AsyncClient, password: str = ADMIN_PASSWORD) -> httpx.Response:
    """Sign the admin in; the client keeps the cookie for the admin routes."""
    body = {"username": ADMIN_USERNAME, "password": password}
    return await http.post("/v1/admin/session", json=body)
