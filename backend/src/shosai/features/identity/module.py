"""The identity slice as composition sees it (identity plan §3.1).

Built in every role: the API serves registration, the workers run the sweeps, the
scheduler queues them. The password pool and the captcha client open and close with the
process.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.features import CoreServices, FeatureModule, FeatureParts
from shosai.features.identity.application.registration import Registration, RegistrationServices
from shosai.features.identity.application.verification import Verification
from shosai.features.identity.channels.http.registration import build_registration_router
from shosai.features.identity.channels.tasks import PERIODIC_JOBS, task_handlers
from shosai.features.identity.contracts import IDENTITY_EVENTS
from shosai.features.identity.emails.registration_attempt import REGISTRATION_ATTEMPT
from shosai.features.identity.emails.registration_code import REGISTRATION_CODE
from shosai.features.identity.infrastructure.captcha import open_captcha
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.password_hasher import PasswordHasher
from shosai.features.identity.infrastructure.records import IDENTITY_MODELS
from shosai.features.identity.infrastructure.registration_routes import RegistrationRoutes
from shosai.features.identity.settings import IdentitySettings, identity_secrets_safe

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
    ),
)


@asynccontextmanager
async def build(services: CoreServices) -> AsyncIterator[FeatureParts]:
    """Open the password pool and the captcha; build the routes and the sweeps."""
    settings = services.settings.features.get(IdentitySettings)
    directory = Directory(services.transactions, services.cache)
    hasher = PasswordHasher(settings.identity_password_hash_rounds)
    try:
        async with open_captcha(settings.identity_turnstile_secret_key) as captcha:
            registration_services = RegistrationServices(
                transactions=services.transactions,
                directory=directory,
                routes=RegistrationRoutes(services.valkey),
                hasher=hasher,
                email=services.email,
                captcha=captcha,
                limiter=services.rate_limiter,
                directory_key=settings.identity_directory_hmac_key.get_secret_value().encode(),
            )
            router = build_registration_router(
                Registration(registration_services),
                Verification(registration_services, services.outbox),
                services.rate_limiter,
            )
            yield FeatureParts(
                http_routers=(router,),
                task_handlers=task_handlers(services.transactions, directory),
                periodic_jobs=PERIODIC_JOBS,
                email_templates=(REGISTRATION_CODE, REGISTRATION_ATTEMPT),
            )
    finally:
        hasher.close()


IDENTITY: Final = FeatureModule(
    name="identity",
    build=build,
    models=IDENTITY_MODELS,
    events=IDENTITY_EVENTS,
    production_checks=(identity_secrets_safe,),
    settings=(IdentitySettings,),
    account_data=(IDENTITY_ACCOUNT_DATA,),
)
