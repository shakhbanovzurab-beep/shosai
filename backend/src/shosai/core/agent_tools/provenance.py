"""Where untrusted text in a tool's result comes from: the label Leo wraps it with (Leo §7.4).

A slice's spec names the label of its tool's results, and a result may name a narrower one of
its own — a file the person owns, where the spec's label is a colleague's file; Leo wraps the
text with it and raises the run's taint.
"""

from enum import StrEnum


class Provenance(StrEnum):
    """Where untrusted text in a result comes from: the label Leo wraps it with (Leo §7.4).

    A closed set, never attacker text; an external MCP server's label is the agent's,
    `mcp:<server>`, since a slice's spec cannot know the server.
    """

    MAIL = "mail"
    WEB = "web"
    FILE_FOREIGN = "file:foreign"
    FILE_OWN = "file:own"
    MEETING_SPEECH = "meeting:speech"
    # Текст задач, которого человек не писал: коллеги, встречи через извлечение, Jira.
    TASK_FOREIGN = "task:foreign"
    MEMORY = "memory"
    SKILL_USER = "skill:user"
