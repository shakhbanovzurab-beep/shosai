"""The draft's shapes of the native meeting routes (D1 gate, S04).

The macOS and Windows 1.4.5 clients send and decode these; the D1 gate compares every
property, its requiredness and its type with the draft's OpenAPI, component names
included. Requests accept unknown fields, as the draft did: the desktop's audio upload
sends one the draft never declared, and refusing it would break the client.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """A new meeting: its title and the device it is recorded on (the machine's name)."""

    title: Annotated[str, Field(max_length=256)]
    client_device_id: str


class SessionUpdate(BaseModel):
    """A change of a meeting: its title, or its end with the client's time of it."""

    title: Annotated[str | None, Field(max_length=256)] = None
    status: Literal["active", "paused", "completed", "failed"] | None = None
    ended_at: datetime | None = None


class SessionResponse(BaseModel):
    """A meeting as the draft answered it; the clients read its `id`."""

    id: UUID
    title: str
    started_at: datetime
    ended_at: datetime | None
    status: str
    client_device_id: str
    created_at: datetime
    updated_at: datetime | None
