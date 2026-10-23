"""The base of tasks' response shapes (tasks plan step 9).

The server always sends every field of a response, defaults included, so the contract
requires them: the cabinet's generated types then match what arrives, with no field that
is optional only on paper.
"""

from pydantic import BaseModel, ConfigDict


class Out(BaseModel):
    """A response shape: a field with a default is still always sent."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
