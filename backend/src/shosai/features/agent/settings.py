"""The agent slice's settings (`AGENT_*`) and their production check (ADR 0068 AG-D4).

Until studio binds its model routes (agent plan step 18), Leo answers on the standard tier
with the model `AGENT_STANDARD_MODEL` names, through OpenRouter, and hands a call to
`AGENT_STANDARD_FALLBACK_MODEL` when the first is unavailable. Outside development the
standard model is required: without it Leo cannot answer.

LangGraph frames a turn (AG-D14) and brings LangChain's tracer, which would send a turn's
messages to LangSmith when `LANGSMITH_TRACING` or `LANGCHAIN_TRACING_V2` is on. A person's
conversation never leaves the platform that way, so a process with either on does not start,
in any environment.
"""

from collections.abc import Iterator
from typing import Self

from pydantic import model_validator

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.config.gate import GateViolation
from shosai.core.config.loading import Settings
from shosai.core.config.sections import SettingsSection


class AgentSettings(SettingsSection):
    """Which models Leo answers with."""

    # Модель OpenRouter стандартного уровня, например google/gemini-3.8-flash.
    agent_standard_model: str | None = None
    # Запасная модель того же уровня: ей переходит вызов, когда основная недоступна.
    agent_standard_fallback_model: str | None = None
    # Трассировка LangChain в LangSmith: разговоры не уходят с платформы, поэтому всегда выключена.
    langsmith_tracing: bool = False
    langchain_tracing_v2: bool = False

    @model_validator(mode="after")
    def no_tracing_outside(self) -> Self:
        """Refuse LangSmith tracing: it would send a person's conversation off the platform."""
        if self.langsmith_tracing or self.langchain_tracing_v2:
            message = "трассировка LangSmith выключена всегда: разговоры не покидают платформу"
            raise ValueError(message)
        return self

    def standard_route(self) -> ModelRoute | None:
        """The standard tier's route, or None while no model is set."""
        if not self.agent_standard_model:
            return None
        fallbacks = (
            (ModelRef(Provider.OPENROUTER, self.agent_standard_fallback_model),)
            if self.agent_standard_fallback_model
            else ()
        )
        return ModelRoute(ModelRef(Provider.OPENROUTER, self.agent_standard_model), fallbacks)


def agent_model_set(settings: Settings) -> Iterator[GateViolation]:
    """Outside development Leo has its standard model."""
    if not settings.features.get(AgentSettings).agent_standard_model:
        yield GateViolation(
            "AGENT_STANDARD_MODEL", "без модели стандартного уровня Leo не отвечает"
        )
