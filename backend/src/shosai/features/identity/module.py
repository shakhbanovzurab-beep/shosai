"""The identity slice as composition sees it (identity plan §3.1).

Built in every role: the API serves registration, the workers run the sweeps, the
scheduler queues them. The password pool and the captcha client open and close with the
process.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from fastapi import APIRouter

from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.identity.application.authentication import TokenAuthenticator
from shosai.features.identity.application.desktop import DesktopSignIn
from shosai.features.identity.application.devices import Devices
from shosai.features.identity.application.native_me import NativeMe
from shosai.features.identity.application.passwords import Passwords, PasswordServices
from shosai.features.identity.application.registration import Registration, RegistrationServices
from shosai.features.identity.application.sessions import Sessions
from shosai.features.identity.application.sign_in import SignIn, SignInServices
from shosai.features.identity.application.verification import Verification
from shosai.features.identity.channels.http.cookies import CookiePolicy
from shosai.features.identity.channels.http.desktop import build_desktop_router
from shosai.features.identity.channels.http.devices import build_devices_router
from shosai.features.identity.channels.http.passwords import build_password_router
from shosai.features.identity.channels.http.registration import build_registration_router
from shosai.features.identity.channels.http.sessions import SessionRoutes, build_session_router
from shosai.features.identity.channels.tasks import PERIODIC_JOBS, task_handlers
from shosai.features.identity.contracts import AUTHENTICATOR, IDENTITY_EVENTS
from shosai.features.identity.emails.password_reset import RESET_LINK_MAIL
from shosai.features.identity.emails.registration_attempt import REGISTRATION_ATTEMPT
from shosai.features.identity.emails.registration_code import REGISTRATION_CODE
from shosai.features.identity.infrastructure.account_markers import AccountMarkers
from shosai.features.identity.infrastructure.captcha import open_captcha
from shosai.features.identity.infrastructure.desktop_codes import DesktopCodes
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from shosai.features.identity.infrastructure.records import IDENTITY_MODELS
from shosai.features.identity.infrastructure.registration_routes import RegistrationRoutes
from shosai.features.identity.infrastructure.session_records import SESSION_MODELS
from shosai.features.identity.infrastructure.sign_in_failures import SignInFailures
from shosai.features.identity.infrastructure.token_codec import TokenCodec
from shosai.features.identity.settings import IdentitySettings, identity_secrets_safe
from shosai.features.identity.social_wiring import social_routers

# Страница кабинета, на которую ведёт ссылка сброса пароля (SM-7).
RESET_PAGE: Final = "/app/reset"
# Что identity хранит о человеке и что с этим делает стирание (§14 п. 7, ADR 0045 п. 7).
IDENTITY_ACCOUNT_DATA: Final = AccountDataSpec(
    owner="identity",
    tables=(
        # Аккаунт обезличивается, а не удаляется: на него ссылаются денежные строки (402-ФЗ).
        TableCoverage("users", Treatment.KEEP_BY_LAW),
        TableCoverage("user_consents", Treatment.ERASE),
        # Живёт 15 минут, удаляется подтверждением или обходом.
        TableCoverage("pending_registrations", Treatment.EXPIRES),
        TableCoverage("directory_entries", Treatment.ERASE),
        TableCoverage("refresh_sessions", Treatment.ERASE),
        TableCoverage("login_events", Treatment.ERASE),
        TableCoverage("password_reset_tokens", Treatment.ERASE),
        TableCoverage("user_identities", Treatment.ERASE),
    ),
)


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Open the password pool and the captcha; build the routes, the sweeps and the ports."""
    settings = services.settings.features.get(IdentitySettings)
    directory = Directory(services.transactions, services.cache)
    hasher = PasswordHasher(settings.identity_password_hash_rounds)
    keys = settings.token_keys()
    codec = TokenCodec(keys)
    directory_key = settings.identity_directory_hmac_key.get_secret_value().encode()
    cookies = CookiePolicy(settings.identity_cookie_secure, settings.identity_cookie_domain)
    routes = RegistrationRoutes(services.valkey)
    sessions = Sessions(
        services.transactions, directory, codec, keys[0].secret.get_secret_value().encode()
    )
    try:
        async with (
            open_captcha(settings.identity_turnstile_secret_key) as captcha,
            social_routers(services, settings, directory, sessions, cookies) as social,
        ):
            registration_services = RegistrationServices(
                transactions=services.transactions, directory=directory, routes=routes,
                hasher=hasher, email=services.email, captcha=captcha,
                limiter=services.rate_limiter, directory_key=directory_key,
            )  # fmt: skip
            sign_in = SignIn(
                SignInServices(
                    transactions=services.transactions, directory=directory, routes=routes,
                    hasher=hasher, captcha=captcha, failures=SignInFailures(services.valkey),
                    sessions=sessions, directory_key=directory_key,
                )
            )  # fmt: skip
            markers = AccountMarkers(services.valkey)
            authenticator = TokenAuthenticator(codec, directory, markers)
            passwords = Passwords(
                PasswordServices(
                    transactions=services.transactions, directory=directory, hasher=hasher,
                    email=services.email, captcha=captcha, limiter=services.rate_limiter,
                    markers=markers, outbox=services.outbox, sessions=sessions,
                    directory_key=directory_key,
                    reset_page=str(services.settings.email.public_base_url).rstrip("/")
                    + RESET_PAGE,
                )
            )  # fmt: skip
            yield FeatureParts(
                http_routers=(
                    build_registration_router(
                        Registration(registration_services),
                        Verification(registration_services, services.outbox, sessions),
                        services.rate_limiter,
                        cookies,
                    ),
                    build_session_router(
                        SessionRoutes(
                            sign_in=sign_in,
                            sessions=sessions,
                            me=NativeMe(services.transactions, services.ports),
                            ports=services.ports,
                            limiter=services.rate_limiter,
                            cookies=cookies,
                        )
                    ),
                    *_account_routers(services, passwords, sessions, markers, cookies),
                    *social,
                ),
                task_handlers=task_handlers(services.transactions, directory),
                periodic_jobs=PERIODIC_JOBS,
                email_templates=(REGISTRATION_CODE, REGISTRATION_ATTEMPT, RESET_LINK_MAIL),
                provides=(AUTHENTICATOR.bind(authenticator),),
            )
    finally:
        hasher.close()


def _account_routers(
    services: CoreServices,
    passwords: Passwords,
    sessions: Sessions,
    markers: AccountMarkers,
    cookies: CookiePolicy,
) -> tuple[APIRouter, ...]:
    """The routes of passwords, desktop sign-in and devices."""
    desktop = DesktopSignIn(services.transactions, DesktopCodes(services.valkey), sessions)
    devices = Devices(services.transactions, markers, services.outbox)
    return (
        build_password_router(passwords, services.ports, services.rate_limiter, cookies),
        build_desktop_router(desktop, services.ports, services.rate_limiter),
        build_devices_router(devices, services.ports),
    )


IDENTITY: Final = FeatureModule(
    name="identity",
    build=build,
    models=(*IDENTITY_MODELS, *SESSION_MODELS),
    events=IDENTITY_EVENTS,
    production_checks=(identity_secrets_safe,),
    settings=(IdentitySettings,),
    account_data=(IDENTITY_ACCOUNT_DATA,),
)
