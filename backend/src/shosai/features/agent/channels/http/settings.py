"""Settings > Leo: `GET` and `PATCH /v1/agent/settings` (agent plan §3.3, step 3).

The cabinet saves each change as it is made and shows it at once, so `PATCH` takes any
subset of the fields and answers the whole settings as saved. Errors use the platform's
envelope: `leo_model_unavailable` for a model the plan does not offer (only `auto` before
studio), `response_language_invalid` for a language outside the 16, `validation_error` for a
field the contract does not know.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.application.preferences import AgentPreferences
from shosai.features.agent.domain.preferences import (
    PreferenceChanges,
    Preferences,
    ResponseLength,
)
from shosai.features.identity.contracts import Principal, bearer_principal

MODEL_MAX = 200
LANGUAGE_MAX = 10


class AgentSettingsOut(BaseModel):
    """Settings > Leo as saved."""

    leo_model: str = Field(description="`auto`, or a model the person's plan offers.")
    response_language: str = Field(description="`auto` (the interface's), or a language code.")
    response_length: ResponseLength
    web_search: bool
    voice_mode: bool = Field(description="Off also hides the microphone.")
    knowledge_base_search: bool
    connected_services_search: bool


class AgentSettingsPatch(BaseModel):
    """The fields to change; the others stay as they are."""

    model_config = ConfigDict(extra="forbid")

    leo_model: str | None = Field(default=None, min_length=1, max_length=MODEL_MAX)
    response_language: str | None = Field(default=None, min_length=2, max_length=LANGUAGE_MAX)
    response_length: ResponseLength | None = None
    web_search: bool | None = None
    voice_mode: bool | None = None
    knowledge_base_search: bool | None = None
    connected_services_search: bool | None = None


def settings_out(preferences: Preferences) -> AgentSettingsOut:
    """The contract's shape of the settings."""
    return AgentSettingsOut(
        leo_model=preferences.leo_model,
        response_language=preferences.response_language,
        response_length=preferences.response_length,
        web_search=preferences.web_search,
        voice_mode=preferences.voice_mode,
        knowledge_base_search=preferences.knowledge_base_search,
        connected_services_search=preferences.connected_services_search,
    )


def changes_of(body: AgentSettingsPatch) -> PreferenceChanges:
    """The fields the body names; a `null` changes nothing."""
    changes = PreferenceChanges()
    if body.leo_model is not None:
        changes["leo_model"] = body.leo_model
    if body.response_language is not None:
        changes["response_language"] = body.response_language
    if body.response_length is not None:
        changes["response_length"] = body.response_length
    if body.web_search is not None:
        changes["web_search"] = body.web_search
    if body.voice_mode is not None:
        changes["voice_mode"] = body.voice_mode
    if body.knowledge_base_search is not None:
        changes["knowledge_base_search"] = body.knowledge_base_search
    if body.connected_services_search is not None:
        changes["connected_services_search"] = body.connected_services_search
    return changes


def build_settings_router(preferences: AgentPreferences, ports: PortDirectory) -> APIRouter:
    """Settings > Leo."""
    router = APIRouter(prefix="/v1/agent/settings", tags=["agent"])
    signed_in = bearer_principal(ports)

    @router.get("")
    async def get_agent_settings(
        principal: Annotated[Principal, Depends(signed_in)],
    ) -> AgentSettingsOut:
        """Your Settings > Leo."""
        return settings_out(await preferences.read(principal.scope()))

    @router.patch("")
    async def patch_agent_settings(
        principal: Annotated[Principal, Depends(signed_in)], body: AgentSettingsPatch
    ) -> AgentSettingsOut:
        """Change some of your Settings > Leo; the answer is all of them as saved."""
        return settings_out(await preferences.change(principal, changes_of(body)))

    return router
