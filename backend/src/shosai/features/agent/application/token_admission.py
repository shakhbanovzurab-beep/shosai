"""The plan's token decision before a request to the standard model (billing BL-D4).

A Leo turn and a native proxy request ask billing for the route of the next standard request:
spent tokens refuse it with 402 `token_limit` and the limit that ran out, and billing that
cannot be read refuses it with 503 `entitlements_unavailable`.
"""

from http import HTTPStatus

from shosai.core.kernel.errors import AppError
from shosai.core.ports.directory import PortDirectory
from shosai.features.billing.contracts import (
    TOKEN_ALLOWANCE,
    EntitlementsUnavailableError,
    ModelTier,
    TokenRoute,
)
from shosai.features.identity.contracts import Principal

SPENT_DAY = "standard_daily_tokens"


async def standard_tokens(ports: PortDirectory, principal: Principal) -> TokenRoute:
    """The route of the person's next standard request; spent tokens are refused."""
    try:
        decision = await ports.get(TOKEN_ALLOWANCE).decision(
            principal.home, principal.user_id, ModelTier.STANDARD
        )
    except EntitlementsUnavailableError as error:
        raise AppError("entitlements_unavailable", HTTPStatus.SERVICE_UNAVAILABLE) from error
    if decision.route is TokenRoute.STOP:
        limit = decision.reason.value if decision.reason is not None else SPENT_DAY
        raise AppError("token_limit", HTTPStatus.PAYMENT_REQUIRED, params={"limit": limit})
    return decision.route
