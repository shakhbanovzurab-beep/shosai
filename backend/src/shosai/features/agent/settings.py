"""The agent slice's settings (`AGENT_*`) and their production check (ADR 0068 AG-D4).

Until studio binds its model routes (agent plan step 18), Leo answers on the standard tier
with the model `AGENT_STANDARD_MODEL` names, through OpenRouter, and hands a call to
`AGENT_STANDARD_FALLBACK_MODEL` when the first is unavailable; titles and summaries are written
by `AGENT_UTILITY_MODEL`, with its own optional fallback. Outside development both are
required: without the first Leo cannot answer, without the second a thread keeps its first
question as its title and its oldest turns drop out of the context instead of folding.

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
    # Служебная модель: заголовки тредов и сжатие старых ходов в сводку, вне пути ответа.
    agent_utility_model: str | None = None
    agent_utility_fallback_model: str | None = None
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
        return route_of(self.agent_standard_model, self.agent_standard_fallback_model)

    def utility_route(self) -> ModelRoute | None:
        """The utility model's route for titles and summaries, or None while none is set."""
        return route_of(self.agent_utility_model, self.agent_utility_fallback_model)


def route_of(model: str | None, fallback: str | None) -> ModelRoute | None:
    """A route through OpenRouter: the model, then its fallback when one is set."""
    if not model:
        return None
    fallbacks = (ModelRef(Provider.OPENROUTER, fallback),) if fallback else ()
    return ModelRoute(ModelRef(Provider.OPENROUTER, model), fallbacks)


def agent_model_set(settings: Settings) -> Iterator[GateViolation]:
    """Outside development Leo has its standard and its utility model."""
    agent = settings.features.get(AgentSettings)
    if not agent.agent_standard_model:
        yield GateViolation(
            "AGENT_STANDARD_MODEL", "без модели стандартного уровня Leo не отвечает"
        )
    if not agent.agent_utility_model:
        yield GateViolation(
            "AGENT_UTILITY_MODEL", "без служебной модели треды Leo не получают заголовков и сводок"
        )
