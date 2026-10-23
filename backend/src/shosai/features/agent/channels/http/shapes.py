"""The bases of agent's request and response shapes."""

from pydantic import BaseModel, ConfigDict


class Strict(BaseModel):
    """A request body: a field the contract does not know is refused."""

    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    """A response shape: every field is always sent, so the generated types require it."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
