"""Building operators for the process: the role port, the owner's and support's routes."""

from shosai.core.features import CoreServices, FeatureParts
from shosai.features.identity.application.account_states import AccountStates
from shosai.features.identity.application.admin_users import AdminUsers
from shosai.features.identity.application.operators import OperatorRoles, Operators
from shosai.features.identity.channels.http.admin_operators import build_admin_operators_router
from shosai.features.identity.channels.http.admin_users import build_admin_users_router
from shosai.features.identity.contracts import OPERATOR_ROLES
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.directory import Directory


def operator_parts(
    services: CoreServices, directory: tuple[Directory, bytes], markers: AccountMarkers
) -> FeatureParts:
    """What operators add to identity's parts; `directory` comes with its address key."""
    lookup = directory[0]
    transactions, outbox = services.transactions, services.outbox
    operators = Operators(transactions, lookup, outbox, services.locks)
    users = AdminUsers(transactions, directory, services.ai_spend.reports)
    states = AccountStates(transactions, lookup, markers, outbox)
    return FeatureParts(
        http_routers=(
            build_admin_operators_router(operators, services.ports),
            build_admin_users_router(users, states, services.ports),
        ),
        provides=(OPERATOR_ROLES.bind(OperatorRoles(transactions)),),
    )
