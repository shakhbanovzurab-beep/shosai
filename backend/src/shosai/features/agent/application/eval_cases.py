"""A rated turn copied as an evaluation case, as the model saw it (ADR 0068 AG-D13; step 11a).

The case keeps the person's question, each round's calls with the digests the model read, the
answer's sources by kind and title, and the answer — the person's name masked everywhere,
attachments left out — with the run's model, tier, toolsets, the policy's version and the
answer's language. It lives in the person's home beside the rating and never leaves it.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Final

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from shosai.core.ports.directory import PortDirectory
from shosai.features.agent.domain.feedback import mask_names
from shosai.features.agent.domain.threads import MessageRole
from shosai.features.agent.infrastructure.prompts import POLICY
from shosai.features.agent.infrastructure.run_records import AgentRunRecord
from shosai.features.agent.infrastructure.thread_records import AgentMessageRecord
from shosai.features.identity.contracts import ACCOUNT_PROFILE_READER

MESSAGE = AgentMessageRecord
RUN = AgentRunRecord
# Версия политики Leo: случай знает, при каких правилах ответ был дан.
PROMPT_VERSION: Final = "policy-" + hashlib.sha256(POLICY.encode()).hexdigest()[:12]
ROUND_COLUMNS: Final = load_only(
    MESSAGE.role, MESSAGE.text, MESSAGE.tool_calls, MESSAGE.tool_name, MESSAGE.digest
)


@dataclass(frozen=True, slots=True)
class CaseCopy:
    """What a case row keeps besides its rating."""

    case: dict[str, JsonValue]
    language: str
    model: str | None
    tier: str | None
    toolsets: list[str]


def _toolsets(run: AgentRunRecord | None) -> list[str]:
    """The toolsets the run offered: chosen at its start or loaded on the way."""
    routing = run.routing if run is not None else {}
    names = [*routing.get("selected", []), *routing.get("loaded", [])]
    return sorted({str(name) for name in names})


def _rounds(rows: list[AgentMessageRecord], names: list[str]) -> list[JsonValue]:
    """Each model message that called tools, with the digests the model read after it."""
    rounds: list[JsonValue] = []
    for row in rows:
        if row.role == MessageRole.ASSISTANT.value and row.tool_calls:
            calls: list[JsonValue] = [
                {
                    "name": str(call.get("name", "")),
                    "arguments": mask_names(json.dumps(call.get("arguments", {})), names),
                }
                for call in row.tool_calls
            ]
            rounds.append({"text": mask_names(row.text, names), "calls": calls, "results": []})
        elif row.role == MessageRole.TOOL.value and rounds:
            last = rounds[-1]
            digest = str((row.digest or {}).get("text", ""))
            if isinstance(last, dict) and isinstance(last["results"], list):
                last["results"].append(
                    {"tool": row.tool_name or "", "digest": mask_names(digest, names)}
                )
    return rounds


async def case_copy(
    session: AsyncSession, ports: PortDirectory, answer: AgentMessageRecord
) -> CaseCopy:
    """The answer's turn as a case, read in the person's transaction."""
    run = await session.scalar(select(RUN).where(RUN.id == answer.run_id))
    question = await session.scalar(
        select(MESSAGE.text)
        .where(
            MESSAGE.thread_id == answer.thread_id,
            MESSAGE.role == MessageRole.USER.value,
            MESSAGE.created_at < answer.created_at,
        )
        .order_by(MESSAGE.created_at.desc(), MESSAGE.id.desc())
        .limit(1)
    )
    rows: list[AgentMessageRecord] = []
    if run is not None:
        rows = list(
            await session.scalars(
                select(MESSAGE)
                .options(ROUND_COLUMNS)
                .where(
                    MESSAGE.thread_id == answer.thread_id,
                    MESSAGE.run_id == run.id,
                    MESSAGE.created_at >= run.started_at,
                    MESSAGE.id != answer.id,
                )
                .order_by(MESSAGE.created_at, MESSAGE.id)
            )
        )
    profile = await ports.get(ACCOUNT_PROFILE_READER).profile(session, answer.user_id)
    full = profile.display_name if profile is not None else ""
    names = [full, *full.split()]
    sources: list[JsonValue] = [
        {
            "kind": str(source.get("kind", "")),
            "title": mask_names(str(source.get("title", "")), names),
        }
        for source in answer.sources
    ]
    case: dict[str, JsonValue] = {
        "question": mask_names(question or "", names),
        "rounds": _rounds(rows, names),
        "sources": sources,
        "answer": mask_names(answer.text, names),
    }
    language = (run.language if run is not None else None) or (
        profile.language if profile is not None else "en"
    )
    return CaseCopy(
        case=case,
        language=language,
        model=run.model if run is not None else None,
        tier=run.tier if run is not None else None,
        toolsets=_toolsets(run),
    )
