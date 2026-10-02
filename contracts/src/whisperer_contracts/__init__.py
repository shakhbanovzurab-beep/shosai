"""Compatibility harness between the v2 contract and the draft.

Public interface for the tests of v2 slices: load the baseline, build a candidate
from v2 artifacts, check it within the slice's scope and get a report.
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
