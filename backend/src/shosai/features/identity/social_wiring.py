"""Building sign-in without a password for the process: providers, codes, tickets, routes.

Social sign-in and sign-in by an emailed code (ADR 0048) share the consent ticket: a new
person from either path finishes on the same consent screen.
"""

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter

from shosai.core.features import CoreServices
from shosai.features.identity.application.email_sign_in import EmailSignIn, EmailSignInServices
from shosai.features.identity.application.sessions import Sessions
from shosai.features.identity.application.social import SocialServices, SocialSignIn
from shosai.features.identity.application.social_accounts import (
    SocialAccounts,
    SocialAccountServices,
)
from shosai.features.identity.channels.http.cookies import CookiePolicy
from shosai.features.identity.channels.http.email_sign_in import build_email_sign_in_router
from shosai.features.identity.channels.http.social import build_social_router
from shosai.features.identity.channels.http.social_finish import build_social_finish_router
from shosai.features.identity.channels.http.social_widgets import build_social_widgets_router
from shosai.features.identity.domain.social import Provider
from shosai.features.identity.infrastructure.captcha import Captcha
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.email_challenges import (
    ChallengeSeals,
    ChallengeStates,
)
from shosai.features.identity.infrastructure.sign_in_failures import SignInFailures
from shosai.features.identity.infrastructure.social.clients import (
    open_provider_http,
    provider_clients,
)
from shosai.features.identity.infrastructure.social.consent_tickets import ConsentTickets
from shosai.features.identity.infrastructure.social.flows import SocialStates
from shosai.features.identity.settings import IdentitySettings


@asynccontextmanager
async def social_routers(
    services: CoreServices,
    settings: IdentitySettings,
    directory: Directory,
    sessions: Sessions,
    access: tuple[CookiePolicy, Captcha],
) -> AsyncIterator[tuple[APIRouter, ...]]:
    """Social and email-code sign-in routes, with the providers' HTTP client open."""
    cookies, captcha = access
    base_url = str(services.settings.email.public_base_url).rstrip("/")
    signing = settings.token_keys()[0].secret.get_secret_value().encode()
    directory_key = settings.identity_directory_hmac_key.get_secret_value().encode()
    states = SocialStates(services.valkey)
    consent = ConsentTickets(signing)
    async with open_provider_http() as http:
        social = SocialSignIn(
            SocialServices(
                transactions=services.transactions, directory=directory, states=states,
                consent=consent, providers=provider_clients(http, settings, base_url),
                state_key=hashlib.sha256(b"shosai.identity.social_state.v1" + signing).digest(),
                directory_key=directory_key, base_url=base_url,
            )
        )  # fmt: skip
        accounts = SocialAccounts(
            SocialAccountServices(
                transactions=services.transactions, directory=directory, states=states,
                consent=consent, sessions=sessions, outbox=services.outbox,
                directory_key=directory_key,
            )
        )  # fmt: skip
        widget_ids = {
            provider: client_id
            for provider, client_id in (
                (Provider.YANDEX, settings.identity_yandex_client_id),
                (Provider.GOOGLE, settings.identity_google_client_id),
                (Provider.VK, settings.identity_vk_client_id),
            )
            if client_id and social.enabled(provider)
        }
        by_code = EmailSignIn(
            EmailSignInServices(
                transactions=services.transactions, directory=directory,
                seals=ChallengeSeals(signing), states=ChallengeStates(services.valkey),
                consent=consent, captcha=captcha, failures=SignInFailures(services.valkey),
                limiter=services.rate_limiter, email=services.email, sessions=sessions,
                directory_key=directory_key,
            )
        )  # fmt: skip
        yield (
            build_social_router(social, services.rate_limiter, widget_ids),
            build_social_finish_router(accounts, services.rate_limiter, cookies),
            build_social_widgets_router(social, services.rate_limiter),
            build_email_sign_in_router(by_code, services.rate_limiter, cookies),
        )
