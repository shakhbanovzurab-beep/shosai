"""What Leo's evaluation runs: scenarios, their tools' answers and the injection corpora (AG-D8).

A scenario is one question on a page, in the platform's languages, with what each tool the
scenario needs answers — checked against the tool's real output schema when it runs — the
rounds a scripted model plays in CI, and what a good trajectory does: the tools it calls, the
arguments that matter, the words and citations its answer carries. The injection corpora
put hostile text into every channel of untrusted text and play a model that obeys it; the
safety suite then checks that nothing was written, nothing left, and the text stayed wrapped.
Scenarios are data shipped with the slice; the models here only read and check them.
"""

import re
from typing import Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from shosai.core.agent_tools.provenance import Provenance
from shosai.core.agent_tools.sources import SourceKind
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES

CASE_ID: Final = re.compile(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)*")
TOOL_NAME: Final = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")
PAYLOAD_SLOT: Final = "{payload}"
# Метка, по которой проверка находит враждебный текст в контексте модели после экранирования.
CANARY_PREFIX: Final = "EVAL-CANARY-"


class Strict(BaseModel):
    """Data with no field its schema lacks."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class EvalCall(Strict):
    """A tool call: the tool's dotted name and its arguments."""

    tool: str = Field(pattern=TOOL_NAME.pattern)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class EvalRound(Strict):
    """One answer of the scripted model: tool calls, or the text of the answer."""

    calls: tuple[EvalCall, ...] = ()
    say: str | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> Self:
        if bool(self.calls) == (self.say is not None):
            message = "раунд сценария — либо вызовы инструментов, либо текст ответа"
            raise ValueError(message)
        return self


class EvalSource(Strict):
    """A source a tool's answer names."""

    kind: SourceKind
    id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    locator: str | None = None
    quote: str = ""


class EvalFixture(Strict):
    """What a tool answers in a scenario; a narrower label for its text when it has one."""

    output: dict[str, JsonValue]
    sources: tuple[EvalSource, ...] = ()
    provenance: Provenance | None = None


class EvalSubject(Strict):
    """What the scenario's page shows: a meeting, task, board or file, with its words."""

    kind: Literal["meeting", "task", "board", "file"]
    id: UUID
    title: str = Field(min_length=1)
    summary: str | None = None
    # Задача человека или чужая: чужой заголовок модель читает обёрнутым.
    own: bool = True


class EvalExpectation(Strict):
    """What a good trajectory does."""

    # Инструменты, которые должны быть вызваны: в CI — ровно они в порядке первого вызова.
    calls: tuple[str, ...] = ()
    # Инструменты, которых ход не вызывает.
    avoid: tuple[str, ...] = ()
    # Поля аргументов, важные для ответа: первое выполнение инструмента несёт эти значения.
    arguments: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)
    # Слова, которые ответ называет на любом языке: имена, числа, коды.
    mentions: tuple[str, ...] = ()
    cites: bool = False
    # Ход без единого инструмента: приветствие, разговор.
    quiet: bool = False
    # Ход предлагает запись: кончается паузой на карточке, не ответом.
    pauses: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.quiet and (self.calls or self.arguments):
            message = "тихий сценарий не ждёт вызовов инструментов"
            raise ValueError(message)
        unknown = sorted(set(self.arguments) - set(self.calls))
        if unknown:
            message = f"аргументы ждутся от невызванных инструментов: {unknown}"
            raise ValueError(message)
        return self


class EvalScenario(Strict):
    """One question on one page, what the tools answer, and what a good answer does."""

    id: str = Field(pattern=CASE_ID.pattern)
    # Что сценарий проверяет — для отчёта человеку; модель этого не читает.
    summary: str
    page: str | None = None
    subject: EvalSubject | None = None
    questions: dict[str, str]
    fixtures: dict[str, EvalFixture] = Field(default_factory=dict)
    script: tuple[EvalRound, ...]
    expect: EvalExpectation

    @model_validator(mode="after")
    def _complete(self) -> Self:
        problems = []
        unknown = sorted(set(self.questions) - set(SUPPORTED_LANGUAGES))
        if unknown or "en" not in self.questions:
            problems.append(f"вопрос по-английски обязателен, языков платформы нет: {unknown}")
        if not self.script or self.script[-1].say is None:
            problems.append("сценарий модели кончается текстом ответа")
        if any(not text.strip() for text in self.questions.values()):
            problems.append("вопрос сценария не пуст")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def question(self, language: str) -> str:
        """The question in the language, English when the scenario lacks it."""
        return self.questions.get(language) or self.questions["en"]


class EvalScenarios(Strict):
    """The shipped scenarios."""

    scenarios: tuple[EvalScenario, ...]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        ids = [scenario.id for scenario in self.scenarios]
        if len(ids) != len(set(ids)):
            message = "ид сценариев оценки не повторяются"
            raise ValueError(message)
        return self


class InjectionCarrier(Strict):
    """A channel of untrusted text: a tool's call and its answer, `{payload}` where the hostile
    text goes; or the page's subject, whose title carries it."""

    tool: str | None = Field(default=None, pattern=TOOL_NAME.pattern)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    output: dict[str, JsonValue] = Field(default_factory=dict)
    provenance: Provenance | None = None
    subject: EvalSubject | None = None
    page: str | None = None

    @model_validator(mode="after")
    def _one_channel(self) -> Self:
        if (self.tool is None) == (self.subject is None):
            message = "канал — либо ответ инструмента, либо предмет страницы"
            raise ValueError(message)
        return self

    @property
    def channel(self) -> str:
        """The channel's name in the suite: the tool's, or `page.<kind>`."""
        if self.tool is not None:
            return self.tool
        return f"page.{self.subject.kind}" if self.subject is not None else "page"


class InjectionPayload(Strict):
    """A piece of hostile text."""

    id: str = Field(pattern=CASE_ID.pattern)
    text: str = Field(min_length=1)

    @property
    def canary(self) -> str:
        """The mark that finds this payload in the model's context."""
        return f"{CANARY_PREFIX}{self.id}"


class InjectionCorpus(Strict):
    """Channels, payloads, and what a model that obeys them tries."""

    carriers: tuple[InjectionCarrier, ...]
    payloads: tuple[InjectionPayload, ...]
    # Что делает послушная модель: записи, уход данных наружу и проба порчи хода.
    attempts: tuple[EvalCall, ...]
    # Раунд перед попытками: загрузить набор пробы, если маршрут его не предложил.
    prepare: tuple[EvalCall, ...] = ()
    # Чтение без источника после канала: инструмент получает порчу хода и записывает её.
    probe: str = Field(pattern=TOOL_NAME.pattern)
    probe_output: dict[str, JsonValue]
    # Вопрос человека в каждом случае: обычный, враждебен только текст канала.
    question: str = Field(min_length=1)


def with_payload(value: JsonValue, payload: str) -> JsonValue:
    """A carrier's value with the hostile text in every `{payload}` slot."""
    if isinstance(value, str):
        return value.replace(PAYLOAD_SLOT, payload)
    if isinstance(value, list):
        return [with_payload(item, payload) for item in value]
    if isinstance(value, dict):
        return {key: with_payload(item, payload) for key, item in value.items()}
    return value


def carries_payload(value: JsonValue) -> bool:
    """Whether a carrier's answer has a slot for the hostile text."""
    if isinstance(value, str):
        return PAYLOAD_SLOT in value
    if isinstance(value, list):
        return any(carries_payload(item) for item in value)
    if isinstance(value, dict):
        return any(carries_payload(item) for item in value.values())
    return False
