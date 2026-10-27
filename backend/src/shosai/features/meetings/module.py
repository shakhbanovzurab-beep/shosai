"""The meetings slice as composition sees it (meetings plan §3.1).

Step A1 published the contract — the ports calendar binds and uses, and the slice's events —
and the domain: rooms, invitation tokens, principals and their sessions, joining and rights,
calls folded from webhooks, the sweep's rule, the chat, recordings and broadcasts, and what
everyone in a call reads from the SFU. LiveKit's adapter, tables, routes and tasks come with
the plan's next steps.
"""

from shosai.core.features import FeatureModule
from shosai.features.meetings.contracts.events import CallEnded, CallStarted, RecordingReady

MEETINGS = FeatureModule(name="meetings", events=(CallStarted, CallEnded, RecordingReady))
