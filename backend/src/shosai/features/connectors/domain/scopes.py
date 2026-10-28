"""Which scopes a flow asks for and whether a grant covers an app (CN-D2, plan §3.4).

A grant is one provider account's consent shared by that account's apps. Connecting another
app asks the provider only for what it adds (Google's incremental authorization), except at
providers that keep one token per account with all its rights (Yandex) or one consent per
person and application (Atlassian): there the flow asks for the union, or the new token
would drop the older apps' rights. After the callback the granted scopes must cover the
app's, since a person may untick a box on Google's consent screen.
"""

from collections.abc import Collection

from shosai.features.connectors.domain.catalogue import AppSpec, Owner


def requested_scopes(
    app: AppSpec,
    owner: Owner,
    *,
    held: Collection[str] = (),
    union_required: bool = False,
) -> frozenset[str]:
    """The scopes the authorize URL names for `app`.

    `held` are the scopes of the account's existing grant at the same application;
    `union_required` comes from the provider's descriptor.
    """
    needed = app.scopes_for(owner)
    return needed | frozenset(held) if union_required else needed


def missing_scopes(app: AppSpec, owner: Owner, granted: Collection[str]) -> frozenset[str]:
    """The app's scopes the grant does not hold; empty when the grant covers the app."""
    return app.scopes_for(owner) - frozenset(granted)


def covers(app: AppSpec, owner: Owner, granted: Collection[str]) -> bool:
    """Whether a grant with `granted` scopes serves the app."""
    return not missing_scopes(app, owner, granted)


def merged_scopes(held: Collection[str], granted: Collection[str]) -> frozenset[str]:
    """The scopes a grant holds after a new token of the same account arrives.

    A provider that returns the whole consent with the token (Google with
    `include_granted_scopes`, Yandex, Atlassian) is read as it says; one that returns only the
    new scopes keeps the older ones, which stay granted at the provider.
    """
    return frozenset(held) | frozenset(granted)


def parse_scope(value: str | None, separator: str = " ") -> frozenset[str]:
    """The scopes of a token response's `scope` field."""
    if not value:
        return frozenset()
    return frozenset(part for part in (item.strip() for item in value.split(separator)) if part)
