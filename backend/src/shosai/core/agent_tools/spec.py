"""`ToolSpec`: what Leo may call, declared by the slice that owns it (ADR 0029, Leo §8.1).

A spec is the model-facing half of a tool: its namespaced name, its toolset, an English
description, Pydantic input and output models, and the gates around it — effect,
reversibility, cost class, entitlement and switch, result budget and timeout, the client
query domains it invalidates, and the provenance of the untrusted text its result carries
(Leo §7.4), which the agent wraps the result with and raises the run's taint by. It holds
no code: the slice binds handlers to it when it is built (`bindings`). A slice declares its
specs on its `FeatureModule`, so the model-facing English test reads every description and
schema without starting anything. A spec also names the one argument a step line shows
(`step_detail`) and, for a write, the wording of the preview keys it returns (`previews`,
ADR 0068): the person's words, never the model's. An egress tool has one wording, which the
agent fills from the call's arguments when the call waits for a card (Leo §7.4).

Rules are checked when a spec is built: a malformed spec stops composition, not a turn.
The input model forbids extra fields: an argument the schema lacks is one the model made up.
The name is `<namespace>.<tool>` in snake_case; how it is spelled on the wire is the
agent's adapter's concern (providers allow no dot). How many tools a toolset holds is
checked by the agent's registry.
"""

import re
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, JsonValue

from shosai.core.agent_tools.previews import PreviewWording
from shosai.core.agent_tools.provenance import Provenance

TOOL_NAME: Final = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")
GATE_NAME: Final = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*")
MAX_NAME: Final = 60
MAX_DESCRIPTION: Final = 1024
MAX_RESULT_BUDGET: Final = 32_000
LONGEST_TIMEOUT: Final = timedelta(seconds=120)


class ToolEffect(StrEnum):
    """What a call does to the world (Leo §8.1)."""

    READ = "read"
    # Читает, но отправляет данные наружу: веб, генерация картинок, внешний MCP.
    EGRESS = "egress"
    WRITE = "write"
    # Действие в кабинете: навигация, тема.
    CLIENT = "client"


# Вызовы, которые ждут карточки человека: запись всегда, выход наружу — в заражённом прогоне.
CARD_EFFECTS: Final = frozenset({ToolEffect.WRITE, ToolEffect.EGRESS})


class Reversibility(StrEnum):
    """How a write can be taken back; it decides which channels may approve it."""

    REVERSIBLE = "reversible"
    COMPENSABLE = "compensable"
    IRREVERSIBLE = "irreversible"


class CostClass(StrEnum):
    """Whether a call spends money beyond the turn's model calls."""

    FREE = "free"
    METERED = "metered"


@dataclass(frozen=True, slots=True)
class ToolSpec[I: BaseModel, O: BaseModel]:
    """One tool as the model and the agent see it."""

    name: str
    toolset: str
    description: str
    input: type[I]
    output: type[O]
    effect: ToolEffect
    cost_class: CostClass = CostClass.FREE
    reversibility: Reversibility | None = None
    entitlement: str | None = None
    switch: str | None = None
    # Сколько токенов результата попадает в контекст; сверх — дайджест и ссылка (ADR 0029 п. 5).
    result_budget: int = 2_000
    timeout: timedelta = timedelta(seconds=10)
    invalidates: tuple[str, ...] = field(default_factory=tuple)
    # Метка недоверенного текста в результате; None — только слова и данные самого человека.
    provenance: Provenance | None = None
    # Аргумент, который показывает строка шага («Поиск встреч: бюджет»); None — без детали.
    step_detail: str | None = None
    # Формулировки ключей превью записи на 16 языках: по ним агент рисует карточку.
    previews: tuple[PreviewWording, ...] = ()

    def __post_init__(self) -> None:
        for problem in _problems(self):
            message = f"инструмент {self.name!r}: {problem}"
            raise ValueError(message)

    def input_schema(self) -> dict[str, JsonValue]:
        """The JSON schema of the arguments, as the model receives it."""
        return self.input.model_json_schema()


def _problems(spec: ToolSpec[Any, Any]) -> list[str]:
    """What is wrong with a spec, in Russian for the engineer."""
    problems = [*_naming_problems(spec), *_effect_problems(spec), *_card_problems(spec)]
    if not 0 < spec.result_budget <= MAX_RESULT_BUDGET:
        problems.append(f"бюджет результата — от 1 до {MAX_RESULT_BUDGET} токенов")
    if not timedelta(0) < spec.timeout <= LONGEST_TIMEOUT:
        problems.append("тайм-аут вызова — больше нуля и не дольше 120 с")
    return problems


def _naming_problems(spec: ToolSpec[Any, Any]) -> list[str]:
    problems: list[str] = []
    if not TOOL_NAME.fullmatch(spec.name) or len(spec.name) > MAX_NAME:
        problems.append("имя — «пространство.инструмент» в snake_case, до 60 символов")
    if not GATE_NAME.fullmatch(spec.toolset):
        problems.append("toolset — имя в snake_case")
    if not spec.description.strip() or len(spec.description) > MAX_DESCRIPTION:
        problems.append("описание обязательно и не длиннее 1024 символов")
    gates = (spec.entitlement, spec.switch, *spec.invalidates)
    if any(gate is not None and not GATE_NAME.fullmatch(gate) for gate in gates):
        problems.append("entitlement, switch и invalidates — имена в snake_case через точку")
    # Лишний аргумент — признак выдуманного моделью поля: модель входа его не принимает.
    if spec.input.model_config.get("extra") != "forbid":
        problems.append("модель входа объявляет extra='forbid'")
    return problems


def _effect_problems(spec: ToolSpec[Any, Any]) -> list[str]:
    problems: list[str] = []
    is_write = spec.effect is ToolEffect.WRITE
    if is_write != (spec.reversibility is not None):
        problems.append("обратимость указывается у записи и только у неё")
    # Выход наружу всегда тарифицируется и при заражённом прогоне требует карточки (§7.4).
    if spec.effect is ToolEffect.EGRESS and spec.cost_class is not CostClass.METERED:
        problems.append("egress-инструмент всегда metered")
    if spec.invalidates and spec.effect is not ToolEffect.WRITE:
        problems.append("invalidates есть только у записи: чтение данных клиента не меняет")
    return problems


def _card_problems(spec: ToolSpec[Any, Any]) -> list[str]:
    problems: list[str] = []
    if spec.step_detail is not None and spec.step_detail not in spec.input.model_fields:
        problems.append("step_detail — имя поля модели входа")
    if spec.previews and spec.effect not in CARD_EFFECTS:
        problems.append("формулировки превью есть только у записи и выхода наружу")
    # Карточку вызова наружу агент заполняет его аргументами: одна формулировка, поля входа.
    if spec.effect is ToolEffect.EGRESS and (
        len(spec.previews) != 1 or not set(spec.previews[0].params) <= set(spec.input.model_fields)
    ):
        problems.append("у выхода наружу одна формулировка карточки, её параметры — поля входа")
    keys = [wording.key for wording in spec.previews]
    prefix = f"agent.{spec.name.split('.', 1)[0]}."
    if len(set(keys)) != len(keys) or not all(key.startswith(prefix) for key in keys):
        problems.append(f"ключи превью разные и начинаются с {prefix}")
    return problems
