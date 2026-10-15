"""Sign-in without a password over the slot: social doubles and the emailed code (ADR 0048)."""

from collections.abc import Mapping

from fastapi import APIRouter
from prometheus_client import CollectorRegistry
from pydantic import SecretStr
from redis.asyncio import Redis

from shosai.core.db.transactions import HomeTransactions
from shosai.core.email.port import EmailPort
from shosai.core.events.catalog import EventTypes
from shosai.core.events.outbox import EventOutbox
from shosai.core.kv.metrics import KeyValueMetrics
from shosai.core.kv.rate_limits import RateLimiter
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
from shosai.features.identity.contracts import IDENTITY_EVENTS
from shosai.features.identity.domain.social import Provider
from shosai.features.identity.infrastructure.captcha import Captcha
from shosai.features.identity.infrastructure.directory import Directory
from shosai.features.identity.infrastructure.email_challenges import (
    ChallengeSeals,
    ChallengeStates,
)
from shosai.features.identity.infrastructure.sign_in_failures import SignInFailures
from shosai.features.identity.infrastructure.social.base import SocialProvider
from shosai.features.identity.infrastructure.social.consent_tickets import ConsentTickets
from shosai.features.identity.infrastructure.social.flows import SocialStates
from shosai.features.identity.settings import TokenKey

DIRECTORY_KEY = b"directory-key-of-the-tests-32-bytes!"
SIGNING_KEYS = (TokenKey("k1", SecretStr("signing-key-of-the-identity-tests-32b")),)
COOKIES = CookiePolicy(secure=True, domain=None)


def passwordless_routers(
    transactions: HomeTransactions,
    valkey: Redis,
    accounts_of: tuple[Directory, Sessions],
    doubles: tuple[Mapping[Provider, SocialProvider], Captcha, EmailPort],
) -> tuple[APIRouter, ...]:
    """Social sign-in through the provider doubles and sign-in by code, sharing consent tickets."""
    directory, sessions = accounts_of
    providers, captcha, email = doubles
    signing = SIGNING_KEYS[0].secret.get_secret_value().encode()
    states = SocialStates(valkey)
    consent = ConsentTickets(signing)
    limiter = RateLimiter(valkey, KeyValueMetrics(CollectorRegistry()))
    social = SocialSignIn(
        SocialServices(
            transactions=transactions, directory=directory, states=states, consent=consent,
            providers=dict(providers), state_key=b"social-state-key-of-the-tests-32b",
            directory_key=DIRECTORY_KEY, base_url="https://shosai.example",
        )
    )  # fmt: skip
    accounts = SocialAccounts(
        SocialAccountServices(
            transactions=transactions, directory=directory, states=states, consent=consent,
            sessions=sessions, outbox=EventOutbox(EventTypes(list(IDENTITY_EVENTS))),
            directory_key=DIRECTORY_KEY,
        )
    )  # fmt: skip
    by_code = EmailSignIn(
        EmailSignInServices(
            transactions=transactions, directory=directory, seals=ChallengeSeals(signing),
            states=ChallengeStates(valkey), consent=consent, captcha=captcha,
            failures=SignInFailures(valkey), limiter=limiter, email=email, sessions=sessions,
            directory_key=DIRECTORY_KEY,
        )
    )  # fmt: skip
    widget_ids = {Provider.YANDEX: "yandex-client", Provider.GOOGLE: "google-client"}
    return (
        build_social_router(social, limiter, widget_ids),
        build_social_finish_router(social, accounts, limiter, COOKIES),
        build_email_sign_in_router(by_code, limiter, COOKIES),
    )
