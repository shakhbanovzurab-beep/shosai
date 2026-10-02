"""Check of a v2 candidate against the draft baseline: the entry point for slices and the CLI.

The check starts from the baseline: every draft endpoint and frame within the scope
must be found in v2 in a compatible form. New v2 endpoints are not checked:
an addition is compatible by definition (§10: changes are additive only).
"""

from dataclasses import dataclass, field

from whisperer_contracts.http_check import (
    compare_operation,
    normalize_path,
    operations,
    response_is_untyped,
)
from whisperer_contracts.inputs import Baseline, BaselineOperation, Candidate, Scope
from whisperer_contracts.jsonvalue import ContractInputError, JsonObject
from whisperer_contracts.model import (
    CompatClass,
    Coverage,
    Difference,
    Finding,
    Impact,
    Report,
    locate,
)
from whisperer_contracts.schema_compare import DocumentPair
from whisperer_contracts.schema_shape import SchemaDocument
from whisperer_contracts.ws_catalogue import Endpoint
from whisperer_contracts.ws_check import (
    compare_connection,
    compare_frame,
    frame_class,
    frame_subject,
)


@dataclass(slots=True)
class _Run:
    """Accumulator of one check run."""

    findings: list[Finding] = field(default_factory=list)
    operations: int = 0
    routes: int = 0
    endpoints: int = 0
    frames: int = 0
    untyped: int = 0

    def add(
        self,
        differences: list[Difference],
        subject: str,
        compat_class: CompatClass,
        slice_id: str,
    ) -> None:
        self.findings += [locate(item, subject, compat_class, slice_id) for item in differences]


def check(
    baseline: Baseline,
    candidate: Candidate,
    scope: Scope | None = None,
    acceptances: dict[str, str] | None = None,
) -> Report:
    """Compare v2 artifacts with the draft baseline within the given scope."""
    area = scope or Scope()
    run = _Run()
    in_scope = [
        item
        for item in baseline.operations
        if item.compat_class is not CompatClass.EXCLUDED and area.includes(item.slice_id, item.path)
    ]
    if candidate.openapi is not None:
        _check_operations(baseline, candidate, candidate.openapi, in_scope, run)
    if candidate.routes is not None:
        _check_routes(candidate.routes, candidate.openapi, in_scope, run)
    if candidate.websocket is not None:
        endpoints = [item for item in baseline.websocket if area.includes(item.slice_id, item.path)]
        _check_websocket(endpoints, candidate.websocket, run)
    return _apply_acceptances(run, acceptances or {})


def _check_operations(
    baseline: Baseline,
    candidate: Candidate,
    candidate_openapi: JsonObject,
    in_scope: list[BaselineOperation],
    run: _Run,
) -> None:
    """Operations from the draft OpenAPI against the v2 OpenAPI."""
    documents = DocumentPair(SchemaDocument(baseline.openapi), SchemaDocument(candidate_openapi))
    draft_operations = operations(baseline.openapi)
    candidate_operations = operations(candidate_openapi)
    for item in in_scope:
        if not item.in_openapi:
            continue
        draft = draft_operations.get(item.key)
        if draft is None:
            raise ContractInputError(f"baseline lists {item.subject} as in OpenAPI, but it is not")
        run.operations += 1
        run.untyped += response_is_untyped(documents.draft, draft)
        current = candidate_operations.get(item.key)
        if current is not None:
            differences = compare_operation(documents, draft, current)
        elif candidate.routes is not None and item.key in candidate.routes:
            differences = [_NOT_IN_OPENAPI]
        else:
            differences = [_MISSING]
        run.add(differences, item.subject, item.compat_class, item.slice_id)


_NOT_IN_OPENAPI = Difference(
    "operation.not_in_openapi",
    Impact.RISKY,
    "",
    "v2 serves this route but leaves it out of OpenAPI, so its shape cannot be verified",
)
_MISSING = Difference("operation.missing", Impact.BREAKING, "", "v2 does not serve this operation")


def _check_routes(
    routes: frozenset[tuple[str, str]],
    candidate_openapi: JsonObject | None,
    in_scope: list[BaselineOperation],
    run: _Run,
) -> None:
    """Routes outside OpenAPI (pages, links, service endpoints), against the v2 route snapshot."""
    documented = set(operations(candidate_openapi)) if candidate_openapi is not None else set()
    for item in in_scope:
        if item.in_openapi:
            continue
        run.routes += 1
        if item.key not in routes and item.key not in documented:
            run.add(
                [Difference("route.missing", Impact.BREAKING, "", "v2 does not serve this route")],
                item.subject,
                item.compat_class,
                item.slice_id,
            )


def _check_websocket(endpoints: list[Endpoint], candidate: tuple[Endpoint, ...], run: _Run) -> None:
    """Draft WebSocket endpoints and frames against the v2 catalogue."""
    candidate_endpoints = {normalize_path(item.path): item for item in candidate}
    for draft in endpoints:
        run.endpoints += 1
        endpoint_class = draft.compat_class or CompatClass.UNUSED
        subject = f"WS {draft.path}"
        current = candidate_endpoints.get(normalize_path(draft.path))
        if current is None:
            run.add(
                [
                    Difference(
                        "ws.endpoint_missing",
                        Impact.BREAKING,
                        "",
                        "v2 does not serve this WebSocket",
                    )
                ],
                subject,
                endpoint_class,
                draft.slice_id,
            )
            continue
        run.add(compare_connection(draft, current), subject, endpoint_class, draft.slice_id)
        current_frames = {frame.key: frame for frame in current.frames}
        for frame in draft.frames:
            run.frames += 1
            run.add(
                compare_frame(frame, current_frames.get(frame.key)),
                frame_subject(draft.path, frame),
                frame_class(draft, frame),
                draft.slice_id,
            )


def _apply_acceptances(run: _Run, acceptances: dict[str, str]) -> Report:
    """Accepted deviations stay in the report but stop being errors."""
    used: set[str] = set()
    findings: list[Finding] = []
    for finding in run.findings:
        reason = acceptances.get(finding.finding_id)
        if reason is None:
            findings.append(finding)
        else:
            used.add(finding.finding_id)
            findings.append(finding.accept(reason))
    return Report(
        findings=tuple(findings),
        coverage=Coverage(
            operations=run.operations,
            routes=run.routes,
            websocket_endpoints=run.endpoints,
            websocket_frames=run.frames,
            untyped_responses=run.untyped,
        ),
        unused_acceptances=tuple(sorted(set(acceptances) - used)),
    )
