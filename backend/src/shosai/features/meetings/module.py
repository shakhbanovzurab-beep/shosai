"""The meetings slice as composition sees it (meetings plan §3.1).

Step 1 publishes the contract, the events and the domain; tables, the meeting's lifecycle,
the transcript store, the pipeline and the routes join in the later steps of the plan.
"""

from shosai.core.features import FeatureModule
from shosai.features.meetings.contracts.events import (
    MeetingDeleted,
    MeetingEnded,
    MeetingRestored,
    NotesReady,
)

MEETINGS = FeatureModule(
    name="meetings",
    events=(MeetingEnded, NotesReady, MeetingDeleted, MeetingRestored),
)
