"""Харнесс совместимости контракта v2 с черновиком.

Публичный интерфейс для тестов срезов v2: загрузить базу, собрать кандидата
из артефактов v2, проверить в области среза и получить отчёт.
"""

from whisperer_contracts.check import check
from whisperer_contracts.inputs import (
    Baseline,
    Candidate,
    Scope,
    load_baseline,
    load_candidate,
    parse_acceptances,
    parse_routes,
)
from whisperer_contracts.jsonvalue import ContractInputError
from whisperer_contracts.model import CompatClass, Finding, Report, Severity
from whisperer_contracts.render_report import render_json, render_text
from whisperer_contracts.ws_catalogue import parse_catalogue

__all__ = [
    "Baseline",
    "Candidate",
    "CompatClass",
    "ContractInputError",
    "Finding",
    "Report",
    "Scope",
    "Severity",
    "check",
    "load_baseline",
    "load_candidate",
    "parse_acceptances",
    "parse_catalogue",
    "parse_routes",
    "render_json",
    "render_text",
]
