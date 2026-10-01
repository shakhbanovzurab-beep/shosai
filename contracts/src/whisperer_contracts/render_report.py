"""Отчёт проверки в двух видах: текст для человека и JSON для CI и агентов."""

import json

from whisperer_contracts.inputs import Scope
from whisperer_contracts.model import Finding, Report, Severity

SEVERITY_ORDER = (Severity.ERROR, Severity.WARNING, Severity.INFO)


def _sorted(findings: tuple[Finding, ...]) -> list[Finding]:
    rank = {severity: index for index, severity in enumerate(SEVERITY_ORDER)}
    return sorted(
        findings, key=lambda item: (rank[item.severity], item.subject, item.pointer, item.rule)
    )


def _visible(report: Report, minimum: Severity) -> list[Finding]:
    limit = SEVERITY_ORDER.index(minimum)
    return [
        item for item in _sorted(report.findings) if SEVERITY_ORDER.index(item.severity) <= limit
    ]


def render_text(report: Report, scope: Scope, minimum: Severity = Severity.INFO) -> str:
    """Человекочитаемый отчёт: итог, покрытие, затем находки от ошибок к сведениям."""
    coverage = report.coverage
    accepted = sum(1 for item in report.findings if item.accepted_reason)
    lines = [
        "Contract check against the draft baseline",
        f"Scope: slices {', '.join(sorted(scope.slices)) or 'all'}; "
        f"path prefixes {', '.join(scope.path_prefixes) or 'all'}",
        f"Checked: {coverage.operations} operations "
        f"({coverage.untyped_responses} with untyped draft responses), "
        f"{coverage.routes} non-OpenAPI routes, "
        f"{coverage.websocket_endpoints} WebSocket endpoints, "
        f"{coverage.websocket_frames} frames",
        f"Result: {'COMPATIBLE' if report.is_compatible else 'INCOMPATIBLE'} — "
        f"{report.count(Severity.ERROR)} errors, {report.count(Severity.WARNING)} warnings, "
        f"{report.count(Severity.INFO)} info ({accepted} accepted)",
    ]
    for finding in _visible(report, minimum):
        location = f"{finding.subject}  {finding.pointer}".rstrip()
        lines += [
            "",
            f"{finding.severity.upper():<8}[{finding.compat_class}] {finding.slice_id}  {location}",
            f"        {finding.rule}: {finding.message}",
            f"        id: {finding.finding_id}",
        ]
        if finding.accepted_reason:
            lines.append(f"        accepted: {finding.accepted_reason}")
    if report.unused_acceptances:
        lines += ["", "Acceptances that matched no finding in this scope:"]
        lines += [f"  - {item}" for item in report.unused_acceptances]
    return "\n".join(lines) + "\n"


def render_json(report: Report, scope: Scope, minimum: Severity = Severity.INFO) -> str:
    """Машиночитаемый отчёт с тем же содержанием, что и текстовый."""
    coverage = report.coverage
    document = {
        "compatible": report.is_compatible,
        "scope": {"slices": sorted(scope.slices), "path_prefixes": list(scope.path_prefixes)},
        "coverage": {
            "operations": coverage.operations,
            "untyped_draft_responses": coverage.untyped_responses,
            "routes": coverage.routes,
            "websocket_endpoints": coverage.websocket_endpoints,
            "websocket_frames": coverage.websocket_frames,
        },
        "counts": {severity.value: report.count(severity) for severity in SEVERITY_ORDER},
        "findings": [
            {
                "id": item.finding_id,
                "severity": item.severity.value,
                "impact": item.impact.value,
                "class": item.compat_class.value,
                "slice": item.slice_id,
                "rule": item.rule,
                "subject": item.subject,
                "pointer": item.pointer,
                "message": item.message,
                "accepted_reason": item.accepted_reason,
            }
            for item in _visible(report, minimum)
        ],
        "unused_acceptances": list(report.unused_acceptances),
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
