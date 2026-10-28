"""The cabinet's pages Leo may open (`core.navigate`), as the cabinet's router has them.

On 2026-10-28 the model guessed `/app/tasks` for a backlog page that does not exist, and the
web app opened its "not found" page (the owner's report). A path that is none of these pages
is refused with the whole list, so the model corrects itself; the cabinet's test keeps the
list equal to its router's pages, `:name` standing for an id.
"""

import re
from collections.abc import Mapping
from typing import Final

# Страница → что на ней (английский: читает модель); шаблоны — как в маршрутах кабинета.
CABINET_PAGES: Final[Mapping[str, str]] = {
    "/app/productivity": "the user's day: focus and time",
    "/app/inbox": "the inbox",
    "/app/calendar": "the calendar",
    "/app/kanban": "Kanban boards with all of the user's tasks",
    "/app/notes": "meetings and their notes",
    "/app/notes/:id": "one meeting's notes",
    "/app/meetings": "video meetings",
    "/app/file-manager": "files",
    "/app/file-manager/folders/:folderId": "one folder of files",
    "/app/knowledge-base": "the knowledge base",
    "/app/mail": "mail",
    "/app/hub": "hubs",
    "/app/hub/:hubId": "one hub",
    "/app/studio": "studio",
    "/app/support": "support",
    "/app/upgrade": "plans and upgrades",
    "/app/download": "the desktop and mobile apps",
    "/app/w": "the last workspace",
    "/app/w/new": "a new workspace",
    "/app/w/:workspace": "a workspace's home",
    "/app/w/:workspace/tasks": "a workspace's tasks",
    "/app/w/:workspace/meetings": "a workspace's meetings",
    "/app/w/:workspace/meetings/:id": "one meeting of a workspace",
    "/app/w/:workspace/projects": "a workspace's projects",
    "/app/w/:workspace/projects/:id": "one project of a workspace",
    "/app/w/:workspace/decisions": "a workspace's decisions",
    "/app/w/:workspace/knowledge": "a workspace's knowledge",
    "/app/w/:workspace/members": "a workspace's members",
    "/app/w/:workspace/settings": "a workspace's settings",
}
PAGE_LIST: Final = "; ".join(f"{path} ({about})" for path, about in CABINET_PAGES.items())
_PATTERNS: Final = tuple(
    re.compile("".join(r"[^/]+" if part.startswith(":") else re.escape(part)
                       for part in re.split(r"(:[A-Za-z]+)", page)))
    for page in CABINET_PAGES
)  # fmt: skip


def is_cabinet_page(path: str) -> bool:
    """Whether the path is one of the cabinet's pages, ids filled in."""
    return any(pattern.fullmatch(path) for pattern in _PATTERNS)
