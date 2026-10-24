"""Who is evaluated now, and the slices' tools answered by the scenario (AG-D8).

The model is offered the slices' real tools — their specs, schemas and descriptions, exactly as
a turn offers them — but a call reaches the scenario instead of the slice: its arguments are
checked by the real input schema, its answer by the real output schema, and every call that
reaches a tool is recorded with the run's taint at that moment. A write runs only if the
Action Gateway executes it; the eval never approves one, so an executed write is a finding.
A scenario's data is checked against the specs before it runs, so a stale scenario fails
loudly instead of quietly answering with an error.
"""

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError

from shosai.core.agent_tools.arguments import parse_arguments
from shosai.core.agent_tools.bindings import AgentTool, ReadTool, RunHandler, WriteTool
from shosai.core.agent_tools.context import ToolContext
from shosai.core.agent_tools.results import (
    PlannedEffect,
    Preview,
    ToolError,
    ToolErrorCode,
    ToolResult,
)
from shosai.core.agent_tools.sources import SourceRef
from shosai.core.agent_tools.spec import ToolEffect, ToolSpec
from shosai.features.agent.domain.eval_cases import EvalScenario, EvalSubject
from shosai.features.agent.domain.eval_checks import ToolRun

# Ключ предпросмотра записи в оценке: карточку никто не показывает и не одобряет.
EVAL_PREVIEW = "agent.eval.write"


@dataclass
class Staged:
    """One person's run: the scenario, the language, and the calls that reached a tool."""

    scenario: EvalScenario
    language: str
    runs: list[ToolRun] = field(default_factory=list)


class EvalStage:
    """Who is being evaluated now, and in which scenario."""

    def __init__(self) -> None:
        self._people: dict[UUID, Staged] = {}

    def enter(self, person: UUID, scenario: EvalScenario, language: str) -> Staged:
        """Stage a person for a scenario."""
        staged = Staged(scenario, language)
        self._people[person] = staged
        return staged

    def leave(self, person: UUID) -> None:
        """The person's run is over."""
        self._people.pop(person, None)

    def of(self, person: UUID) -> Staged | None:
        """The person's run, if one is staged."""
        return self._people.get(person)

    def subject(self, person: UUID, kind: str, ids: Collection[UUID]) -> EvalSubject | None:
        """The staged page's subject when it is of the kind and among the ids."""
        staged = self.of(person)
        subject = staged.scenario.subject if staged is not None else None
        if subject is None or subject.kind != kind or subject.id not in ids:
            return None
        return subject


class EvalTools:
    """The slices' specs bound to the scenario's answers."""

    def __init__(self, stage: EvalStage) -> None:
        self._stage = stage

    def bind(self, specs: Iterable[ToolSpec[Any, Any]]) -> tuple[AgentTool, ...]:
        """A tool for each spec: a write planned and never applied unless executed."""
        return tuple(
            self._write(spec)
            if spec.effect is ToolEffect.WRITE
            else ReadTool(spec, self._run(spec))
            for spec in specs
        )

    def _staged(
        self, context: ToolContext, spec: ToolSpec[Any, Any], arguments: BaseModel
    ) -> Staged:
        """The caller's run, with this call recorded."""
        person = context.scope.user_id
        staged = self._stage.of(person) if person is not None else None
        if staged is None:
            message = f"инструмент {spec.name} вызван вне оценки"
            raise LookupError(message)
        argument_values = arguments.model_dump(mode="json")
        staged.runs.append(
            ToolRun(spec.name, spec.effect.value, argument_values, int(context.taint))
        )
        return staged

    def _run(self, spec: ToolSpec[Any, Any]) -> RunHandler[Any, Any]:
        async def run(arguments: BaseModel, context: ToolContext) -> ToolResult[Any]:
            fixture = self._staged(context, spec, arguments).scenario.fixtures.get(spec.name)
            if fixture is None:
                return ToolResult.failed(ToolErrorCode.NOT_FOUND)
            sources = tuple(
                SourceRef(source.kind, source.id, source.title, None, source.locator, source.quote)
                for source in fixture.sources
            )
            output = spec.output.model_validate(fixture.output)
            return ToolResult(output, sources=sources, provenance=fixture.provenance)

        return run

    def _write(self, spec: ToolSpec[Any, Any]) -> WriteTool[Any, Any]:
        async def plan(arguments: BaseModel, context: ToolContext) -> PlannedEffect | ToolError:
            del context
            return PlannedEffect(targets=(spec.name,), data=arguments.model_dump(mode="json"))

        async def preview(planned: PlannedEffect, context: ToolContext) -> Preview:
            del planned, context
            return Preview(EVAL_PREVIEW)

        async def execute(
            planned: PlannedEffect, context: ToolContext, key: str
        ) -> ToolResult[Any]:
            del key
            self._staged(context, spec, spec.input.model_validate(planned.data))
            return ToolResult.failed(ToolErrorCode.FAILED)

        return WriteTool(spec, plan, preview, execute)


def scenario_problems(scenario: EvalScenario, tools: Mapping[str, AgentTool]) -> list[str]:
    """What in a scenario no longer fits the tools: unknown names, answers or calls their
    schemas refuse."""
    problems = []
    for name, fixture in scenario.fixtures.items():
        tool = tools.get(name)
        if tool is None:
            problems.append(f"{scenario.id}: answer of an unknown tool {name}")
            continue
        try:
            tool.spec.output.model_validate(fixture.output)
        except ValidationError as invalid:
            problems.append(f"{scenario.id}: answer of {name} refused: {invalid.error_count()}")
    calls = [call for step in scenario.script for call in step.calls]
    for call in calls:
        tool = tools.get(call.tool)
        if tool is None:
            problems.append(f"{scenario.id}: call of an unknown tool {call.tool}")
        elif isinstance(parse_arguments(tool.spec, call.arguments), ToolError):
            problems.append(f"{scenario.id}: arguments of {call.tool} refused")
    problems += [
        f"{scenario.id}: expects an unknown tool {name}"
        for name in (*scenario.expect.calls, *scenario.expect.avoid)
        if name not in tools
    ]
    return problems
