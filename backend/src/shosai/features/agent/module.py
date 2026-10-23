"""The agent slice as composition sees it (agent plan §3.1).

Step 1 publishes the contract, the event and the domain; the tables, the settings, the
threads, the run on the `agent` queue, the tools, the Action Gateway and the cabinet's
routes join in the later steps.
"""

from shosai.core.features import FeatureModule
from shosai.features.agent.contracts.events import TurnCompleted

AGENT = FeatureModule(name="agent", events=(TurnCompleted,))
