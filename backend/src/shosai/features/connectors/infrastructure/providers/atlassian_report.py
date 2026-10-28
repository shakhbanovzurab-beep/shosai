"""Atlassian's Personal Data Reporting API, which Shosai calls (`POST /app/report-accounts/`).

The request carries the bearer token of a person who went through the app's consent; 204
says nothing is to be done, 200 lists the accounts that were closed or changed. A 401 means
that token is not taken here, and another person's is tried; 429, 5xx and a transport
failure are transient; any other refusal is Shosai's own mistake and fails loudly.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
from typing import Final

import httpx
from pydantic import SecretStr

from shosai.features.connectors.contracts.provider import ProviderUnavailableError
from shosai.features.connectors.domain.account_report import (
    MAX_ACCOUNTS,
    ReportedAccount,
    Verdict,
    cycle_of,
    rfc3339,
)
from shosai.features.connectors.infrastructure.providers.atlassian import API

REPORT_URL: Final = f"{API}/app/report-accounts/"
REPORT_TIMEOUT: Final = httpx.Timeout(20.0, connect=5.0)
VERDICTS: Final = frozenset(Verdict)


@dataclass(frozen=True, slots=True)
class ReportAnswer:
    """Atlassian's verdicts by account id, and the cycle it named."""

    verdicts: Mapping[str, Verdict]
    cycle: timedelta | None


class ReportTokenRefusedError(Exception):
    """Atlassian did not take this person's token for the report; another one is tried."""


class ReportRejectedError(Exception):
    """Atlassian rejected the report itself: Shosai sent it wrong."""


def verdicts_of(body: object) -> dict[str, Verdict]:
    """The verdicts of a 200 answer; an unknown status is not a verdict."""
    accounts = body.get("accounts") if isinstance(body, dict) else None
    found: dict[str, Verdict] = {}
    for item in accounts if isinstance(accounts, list) else []:
        if not isinstance(item, dict):
            continue
        account_id, status = item.get("accountId"), item.get("status")
        if isinstance(account_id, str) and status in VERDICTS:
            found[account_id] = Verdict(status)
    return found


async def report_accounts(
    http: httpx.AsyncClient, token: SecretStr, accounts: Sequence[ReportedAccount]
) -> ReportAnswer:
    """Report one batch of accounts with one person's token."""
    if not 0 < len(accounts) <= MAX_ACCOUNTS:
        message = f"в отчёте от 1 до {MAX_ACCOUNTS} аккаунтов"
        raise ValueError(message)
    body = {"accounts": [
        {"accountId": account.account_id, "updatedAt": rfc3339(account.updated_at)}
        for account in accounts
    ]}  # fmt: skip
    headers = {"Authorization": f"Bearer {token.get_secret_value()}"}
    try:
        response = await http.post(REPORT_URL, json=body, headers=headers, timeout=REPORT_TIMEOUT)
    except httpx.HTTPError:
        raise ProviderUnavailableError from None
    cycle = cycle_of(response.headers.get("Cycle-Period"))
    status = response.status_code
    if status == HTTPStatus.NO_CONTENT:
        return ReportAnswer({}, cycle)
    if status == HTTPStatus.UNAUTHORIZED:
        raise ReportTokenRefusedError
    if status == HTTPStatus.TOO_MANY_REQUESTS or status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        raise ProviderUnavailableError
    if status != HTTPStatus.OK:
        message = f"Atlassian отверг отчёт: {status}"
        raise ReportRejectedError(message)
    try:
        answer = response.json()
    except ValueError:
        message = "Atlassian ответил на отчёт не JSON"
        raise ReportRejectedError(message) from None
    return ReportAnswer(verdicts_of(answer), cycle)
