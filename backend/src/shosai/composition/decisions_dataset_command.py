"""`shosai decisions dataset …`: the labelled sets beside the code (ADR 0069 DL-D8).

    dataset check                                     every point's sets in shape
    dataset generate POINT@VERSION --language L --count N
                                                      synthetic cases, confirmed blind
    dataset draft-reference POINT@VERSION --language ru|en --count N
                                                      cases for a person to label blind
    dataset label-reference POINT@VERSION             the machine's labels beside the person's

Generation and labelling are the platform's own calls of `DECISIONS_GENERATOR_MODEL` and
`DECISIONS_LABELLER_MODEL`; nothing they read is a person's data.
"""

import argparse
from typing import Any, Final, TextIO

from shosai.core.features import CoreServices
from shosai.core.i18n.locales import SUPPORTED_LANGUAGES
from shosai.features.decisions.application.dataset_making import DatasetMaker, Tooling
from shosai.features.decisions.domain.policies import POLICIES, policies_by_key
from shosai.features.decisions.domain.policy import Policy
from shosai.features.decisions.infrastructure.dataset_files import (
    append_synthetic,
    draft_count,
    synthetic_count,
    with_machine_labels,
    write_drafts,
)
from shosai.features.decisions.infrastructure.datasets import point_folder, read_cases, read_sets
from shosai.features.decisions.settings import DecisionsSettings

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
LANGUAGE_CHOICES: Final = (*SUPPORTED_LANGUAGES, "all")


def add_dataset(actions: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """`shosai decisions dataset …`."""
    dataset = actions.add_parser("dataset", help="the labelled sets beside the code")
    tools = dataset.add_subparsers(dest="tool", required=True, metavar="TOOL")
    tools.add_parser("check", help="every point's sets in shape")
    for name, help_text in (
        ("generate", "synthetic cases, written to labels and confirmed blind"),
        ("draft-reference", "cases a person labels blind, in reference/drafts"),
    ):
        tool = tools.add_parser(name, help=help_text)
        tool.add_argument("target", metavar="POINT@VERSION")
        tool.add_argument("--language", required=True, choices=LANGUAGE_CHOICES)
        tool.add_argument(
            "--count", type=int, required=True, choices=range(1, 401), metavar="1..400"
        )
    label = tools.add_parser("label-reference", help="the machine's labels on the reference")
    label.add_argument("target", metavar="POINT@VERSION")


def checked(out: TextIO) -> int:
    """Read every point's sets; name what is off."""
    problems = 0
    for policy in POLICIES:
        try:
            sets = read_sets(policy)
        except ValueError as error:
            problems += 1
            out.write(f"{policy.key}: {error}\n")
            continue
        synthetic, reference = len(sets.synthetic), len(sets.reference)
        out.write(f"{policy.key}: {synthetic} synthetic, {reference} reference\n")
    return EXIT_FAILED if problems else EXIT_OK


async def made(
    services: CoreServices, action: str, target: str, sizing: tuple[str | None, int], out: TextIO
) -> int:
    """Generate, draft or label for one policy version."""
    policy = policies_by_key().get(target)
    if policy is None:
        out.write(f"version {target} is not in this image\n")
        return EXIT_FAILED
    settings = services.settings.features.get(DecisionsSettings)
    maker = DatasetMaker(
        Tooling(services.ai, settings.generator_route(), settings.labeller_route())
    )
    if action == "label":
        return await labelled(maker, policy, out)
    language, count = sizing
    languages = SUPPORTED_LANGUAGES if language == "all" else (language or "",)
    for each in languages:
        await made_in(maker, policy, (each, count, action), out)
    return EXIT_OK


async def made_in(
    maker: DatasetMaker, policy: Policy[Any, Any], job: tuple[str, int, str], out: TextIO
) -> None:
    """One language's generated cases or drafts."""
    language, count, action = job
    offset = (
        draft_count(policy, language) if action == "draft" else synthetic_count(policy, language)
    )
    cases = await maker.generate(policy, language, count, offset)
    if action == "draft":
        path = write_drafts(policy, language, cases)
    else:
        path = append_synthetic(policy, language, cases)
    out.write(f"{policy.key} {language}: {len(cases)} of {count} kept in {path.name}\n")


async def labelled(maker: DatasetMaker, policy: Policy[Any, Any], out: TextIO) -> int:
    """The machine's labels on every reference case of the point."""
    folder = point_folder(policy.point) / "reference"
    for path in sorted(folder.glob("*.jsonl")):
        cases = read_cases(policy, [path])
        labels = {}
        for case in cases:
            machine = await maker.label(policy, case)
            if machine is not None:
                labels[case.id] = machine
        written = with_machine_labels(path, labels)
        out.write(f"{policy.key} {path.stem}: {written} of {len(cases)} labelled\n")
    return EXIT_OK
