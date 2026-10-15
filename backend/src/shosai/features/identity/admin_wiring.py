"""Building the admin panel's backend for the process: the session, the gate, the routes."""

from shosai.core.features import CoreServices, FeatureParts
from shosai.features.identity.application.account_states import AccountStates
from shosai.features.identity.application.admin_access import AdminAccess, AdminCredentials
from shosai.features.identity.application.admin_users import AdminUsers
from shosai.features.identity.channels.http.admin_session import build_admin_session_router
from shosai.features.identity.channels.http.admin_users import build_admin_users_router
from shosai.features.identity.channels.http.cookies import CookiePolicy
from shosai.features.identity.contracts import ADMIN_GATE
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.admin_sessions import AdminSessions
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from shosai.features.identity.settings import IdentitySettings


def admin_parts(
    services: CoreServices,
    directory: tuple[Directory, bytes],
    markers: AccountMarkers,
    access: tuple[PasswordHasher, CookiePolicy],
) -> FeatureParts:
    """What the admin adds to identity's parts; `directory` comes with its address key."""
    hasher, cookies = access
    settings = services.settings.features.get(IdentitySettings)
    username, password_hash = (
        settings.identity_admin_username,
        settings.identity_admin_password_hash,
    )
    credentials = (
        AdminCredentials(username, password_hash)
        if username and password_hash is not None
        else None
    )
    signing = settings.token_keys()[0].secret.get_secret_value().encode()
    admin = AdminAccess(
        credentials, hasher, AdminSessions(services.valkey, signing), services.rate_limiter
    )
    lookup = directory[0]
    users = AdminUsers(services.transactions, directory, services.ai_spend.reports)
    states = AccountStates(services.transactions, lookup, markers, services.outbox)
    return FeatureParts(
        http_routers=(
            build_admin_session_router(admin, services.ports, services.rate_limiter, cookies),
            build_admin_users_router(users, states, services.ports),
        ),
        provides=(ADMIN_GATE.bind(admin),),
    )
