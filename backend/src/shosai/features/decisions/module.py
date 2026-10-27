"""The decisions slice as composition sees it (decisions plan §3.1).

Step 1 published the contract, the domain and the three policies of this plan; step 2 added
the tables — records and outcomes in each home, policies and threshold revisions in the EU
home — and the declaration of what they hold of a person: nothing that outlives its
partition. The engine that binds `DECISION_LAYER` and the agent's ports, and the operator's
command, come with the next steps.
"""

from typing import Final

from shosai.core.account_data.spec import AccountDataSpec, TableCoverage, Treatment
from shosai.core.features import FeatureModule
from shosai.features.decisions.infrastructure.records import (
    DECISION_MODELS,
    DecisionOutcomeRow,
    DecisionRow,
)

# Записи — только идентификаторы, числа и коды без id человека: истекают со своей партицией.
ACCOUNT_DATA: Final = AccountDataSpec(
    "decisions",
    tuple(
        TableCoverage(model.__tablename__, Treatment.EXPIRES)
        for model in (DecisionRow, DecisionOutcomeRow)
    ),
)

DECISIONS = FeatureModule(name="decisions", models=DECISION_MODELS, account_data=(ACCOUNT_DATA,))
