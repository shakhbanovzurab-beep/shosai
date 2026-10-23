"""The base of every request body of tasks: a field the contract does not know is refused."""

from pydantic import BaseModel, ConfigDict


class Strict(BaseModel):
    """A request body: unknown fields are refused."""

    model_config = ConfigDict(extra="forbid")
