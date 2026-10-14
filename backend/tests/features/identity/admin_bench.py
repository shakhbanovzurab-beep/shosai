"""Operators' routes over the identity bench: support's and transfers, which stay closed."""

from fastapi import APIRouter

from shosai.core.ai.spend.reports import SpendReports
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.application.account_states import AccountStates
from shosai.features.identity.application.admin_users import AdminUsers
from shosai.features.identity.application.transfers import Transfers
from shosai.features.identity.channels.http.admin_transfers import build_admin_transfers_router
from shosai.features.identity.channels.http.admin_users import build_admin_users_router
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.directory import Directory


def admin_routers(
    transactions: HomeTransactions,
    directory: tuple[Directory, bytes],
    events: tuple[AccountMarkers, EventOutbox],
    ports: PortDirectory,
) -> tuple[APIRouter, ...]:
    """`/v1/admin/users*` and the transfer routes over the slot's homes."""
    markers, outbox = events
    users = AdminUsers(transactions, directory, SpendReports(transactions))
    states = AccountStates(transactions, directory[0], markers, outbox)
    transfers = Transfers(transactions, directory[0], outbox, allowed=False)
    return (
        build_admin_users_router(users, states, ports),
        build_admin_transfers_router(transfers, ports),
    )
