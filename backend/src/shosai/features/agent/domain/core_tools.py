"""The names of Leo's own tools, which the turn itself acts on (Leo §8.2; agent step 6).

`core.load_toolset` adds a toolset to the run from its next round, and `core.navigate` sends
the cabinet a `client.action`; their handlers only check and echo the request. Both are named
here so the turn knows them without reaching into the channel that binds them.
"""

from typing import Final

READ_RESULT: Final = "core.read_result"
LOAD_TOOLSET: Final = "core.load_toolset"
NAVIGATE: Final = "core.navigate"
