"""The files slice as composition sees it (files plan §3.1).

Step 1 publishes the contract, the events and the domain; tables, uploads, the File
Manager and the quota join in the later steps of the plan.
"""

from shosai.core.features import FeatureModule
from shosai.features.files.contracts.events import (
    FileDeleted,
    FileRestored,
    FileUploaded,
    LeoUseChanged,
)

FILES = FeatureModule(
    name="files",
    events=(FileUploaded, FileDeleted, FileRestored, LeoUseChanged),
)
