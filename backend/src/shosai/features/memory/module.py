"""The memory slice as composition sees it (memory plan §3.1).

Step 1 published the domain — facts and their changes, the trust of a fact, decay, what
reaches a turn, admission, lifetimes, the summary and the "Ask or update" box — the texts the
models read, and the agent's ports memory binds and uses. Tables, routes, recall, admission
and the toolset come with the plan's next steps.
"""

from shosai.core.features import FeatureModule

MEMORY = FeatureModule(name="memory")
