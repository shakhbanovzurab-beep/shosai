"""What the voice model reads from capture itself (ADR 0070): English, registered as model-facing.

The agent writes the instruction and every tool's answer; capture answers a call only when
the agent could not, so the model is never left waiting for a result.
"""

import json
from typing import Final

TOOL_FAILED: Final = json.dumps(
    {
        "error": {
            "code": "unavailable",
            "message": "The tool could not run now. Tell the person in one sentence and go on.",
        }
    }
)

VOICE_TEXTS: Final = (TOOL_FAILED,)
