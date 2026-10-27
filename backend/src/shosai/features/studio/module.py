"""The studio slice as composition sees it (studio plan §3.1, ADR 0074).

Step 1 published the contracts — `MODEL_ROUTES`, `MODEL_CATALOGUE`, `PROMPT_RESOLVER` and the
two events — and the domain: roles, the catalogue and the tier a price proposes, defaults per
role, the resolution of a model, a person's prompts, skills and context, the platform layer
and its versions. The ports are bound when the resolution is built (step 10).
"""

from shosai.core.features import FeatureModule
from shosai.features.studio.contracts.events import STUDIO_EVENTS

STUDIO = FeatureModule(name="studio", events=STUDIO_EVENTS)
