"""Building operators for the process: the role port and the owner's routes."""

from shosai.core.features import CoreServices, FeatureParts
from shosai.features.identity.application.operators import OperatorRoles, Operators
from shosai.features.identity.channels.http.admin_operators import build_admin_operators_router
from shosai.features.identity.contracts import OPERATOR_ROLES
from shosai.features.identity.infrastructure.directory import Directory


def operator_parts(services: CoreServices, directory: Directory) -> FeatureParts:
    """What operators add to identity's parts."""
    operators = Operators(services.transactions, directory, services.outbox, services.locks)
    return FeatureParts(
        http_routers=(build_admin_operators_router(operators, services.ports),),
        provides=(OPERATOR_ROLES.bind(OperatorRoles(services.transactions)),),
    )
