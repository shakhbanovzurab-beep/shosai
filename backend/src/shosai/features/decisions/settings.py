"""The decisions slice's settings (`DECISIONS_*`, decisions plan §3.2).

`DECISIONS_JEV_MODEL` is the pinned Jev snapshot every policy asks — never an alias such as
`~typesafe/jev-latest`, whose answers would change under calibrated thresholds without a
new version (Leo §6.1). `DECISIONS_MAX_IN_FLIGHT` caps the Jev calls one process keeps in
flight, late ones included: past it a decision is the rule's outcome (`busy`), so a slow Jev
can never pile calls up in a process. `DECISIONS_GENERATOR_MODEL` writes the synthetic cases
of the labelled sets and `DECISIONS_LABELLER_MODEL`, of another provider, labels cases blind
(ADR 0069 DL-D8); only the operator's command uses them.
"""

import re
from typing import Final, Self

from pydantic import PositiveInt, model_validator

from shosai.core.ai.calls import ModelRef, ModelRoute, Provider
from shosai.core.config.sections import SettingsSection

PINNED_MODEL: Final = re.compile(r"[a-z0-9_.-]+/[a-z0-9_.-]+")


class DecisionsSettings(SettingsSection):
    """Which Jev answers, and how many calls a process keeps in flight."""

    # Закреплённая версия Jev: от неё зависят откалиброванные пороги.
    decisions_jev_model: str = "typesafe/jev-1.13"
    decisions_max_in_flight: PositiveInt = 64
    # Модель, которая пишет синтетические случаи наборов, и независимая модель другого
    # поставщика, которая размечает их вслепую (DL-D8). Только для команды оператора.
    # Дешёвые по умолчанию: Sonnet и GPT-5.6 стоили в 20 раз дороже при том же отсеве.
    decisions_generator_model: str = "deepseek/deepseek-v4-flash"
    decisions_labeller_model: str = "minimax/minimax-m3.1-flash"

    @model_validator(mode="after")
    def pinned(self) -> Self:
        """Refuse an alias or a moving name: thresholds are fitted to one snapshot."""
        model = self.decisions_jev_model
        if not PINNED_MODEL.fullmatch(model) or model.endswith("latest"):
            message = "DECISIONS_JEV_MODEL — закреплённая версия Jev, не псевдоним"
            raise ValueError(message)
        return self

    def generator_route(self) -> ModelRoute:
        """The model that writes synthetic cases."""
        return ModelRoute(ModelRef(Provider.OPENROUTER, self.decisions_generator_model))

    def labeller_route(self) -> ModelRoute:
        """The model that labels cases blind."""
        return ModelRoute(ModelRef(Provider.OPENROUTER, self.decisions_labeller_model))

    def jev_route(self) -> ModelRoute:
        """The route of every decision: the pinned model, no fallback of another kind."""
        return ModelRoute(ModelRef(Provider.OPENROUTER, self.decisions_jev_model))
