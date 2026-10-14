"""Support's routes over the identity bench: search, the card and the account actions."""

from fastapi import APIRouter

from shosai.core.ai.spend.reports import SpendReports
from shosai.core.db.transactions import HomeTransactions
from shosai.core.events.outbox import EventOutbox
from shosai.core.ports.directory import PortDirectory
from shosai.features.identity.application.account_states import AccountStates
from shosai.features.identity.application.admin_users import AdminUsers
from shosai.features.identity.channels.http.admin_users import build_admin_users_router
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.directory import Directory


def admin_users_router(
    transactions: HomeTransactions,
    directory: tuple[Directory, bytes],
    events: tuple[AccountMarkers, EventOutbox],
    ports: PortDirectory,
) -> APIRouter:
    """`/v1/admin/users*` over the slot's homes."""
    markers, outbox = events
    users = AdminUsers(transactions, directory, SpendReports(transactions))
    states = AccountStates(transactions, directory[0], markers, outbox)
    return build_admin_users_router(users, states, ports)
