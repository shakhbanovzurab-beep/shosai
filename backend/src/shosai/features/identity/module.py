"""The identity slice as composition sees it (identity plan §3.1).

Step 1 declares the slice's settings, events and production checks; its tables, routes
and port bindings arrive with the steps that build them.
"""

from typing import Final

from shosai.core.features import FeatureModule
from shosai.features.identity.contracts import IDENTITY_EVENTS
from shosai.features.identity.settings import IdentitySettings, identity_secrets_safe

IDENTITY: Final = FeatureModule(
    name="identity",
    events=IDENTITY_EVENTS,
    production_checks=(identity_secrets_safe,),
    settings=(IdentitySettings,),
)
