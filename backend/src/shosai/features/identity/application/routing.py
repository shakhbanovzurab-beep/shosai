"""Valkey's routes of pending registrations, with its outage turned into 503."""

from uuid import UUID

from shosai.core.kernel.homes import Home
from shosai.features.identity.application import registration_errors as errors
from shosai.features.identity.domain.registration import PENDING_LIFETIME
from shosai.features.identity.infrastructure.registration_routes import (
    RegistrationRoutes,
    RegistrationRoutesUnavailableError,
)


async def route_registration(
    routes: RegistrationRoutes, registration_id: UUID, email_hmac: bytes, home: Home
) -> None:
    """Route a registration to its home for its lifetime, or answer 503."""
    try:
        await routes.record(registration_id, email_hmac, home, PENDING_LIFETIME)
    except RegistrationRoutesUnavailableError as error:
        raise errors.registration_unavailable() from error


async def route_of(routes: RegistrationRoutes, registration_id: UUID) -> tuple[Home, bytes] | None:
    """The home and HMAC of a live registration, or answer 503."""
    try:
        return await routes.route(registration_id)
    except RegistrationRoutesUnavailableError as error:
        raise errors.registration_unavailable() from error
