"""The database roles the backend names in its SQL (ADR 0001, ADR 0053 point 2).

The application and migration roles come with each home's addresses; the sweep role has
one name everywhere. It cannot log in: the application role switches to it inside a
transaction of a workers or scheduler process, and row-level security lets it see every
tenant's rows. The server's setup creates it, as it creates the other two roles.
"""

from typing import Final

SWEEPER_ROLE: Final = "shosai_sweeper"
