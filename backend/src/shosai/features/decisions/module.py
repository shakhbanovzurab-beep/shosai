"""The decisions slice as composition sees it (decisions plan §3.1).

Step 1 publishes the contract, the domain and the three policies of this plan; the engine
that binds `DECISION_LAYER` and the agent's ports, the tables and the operator's command come
with the next steps.
"""

from shosai.core.features import FeatureModule

DECISIONS = FeatureModule(name="decisions")
