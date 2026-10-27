"""The Decision Layer's tables (decisions plan §3.6, ADR 0069).

In each home, decisions and what followed them: monthly partitions kept four months, ids,
numbers and codes only, no person's id — so no row-level policy, and the application may
only insert (the daily reliability pass reads them as the sweep role). In the EU home, the
platform's policies in force and their fitted thresholds: data without an owner (§6).
"""

from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    SmallInteger,
    Text,
    Uuid,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase, table_info
from shosai.core.db.partitions.policy import monthly_partition_range
from shosai.core.kernel.homes import Home
from shosai.features.decisions.domain.outcomes import DecisionReason, DecisionSource, SubjectKind

POINT_FORM: Final = "~ '^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$'"
CODE_FORM: Final = "~ '^[a-z0-9_.,:-]+$'"
LANGUAGE_FORM: Final = "~ '^[a-z]{2,3}(-[A-Za-z]{2,4})?$'"
STATES: Final = "'shadow', 'active', 'retired'"


def known(values: type[DecisionReason | DecisionSource | SubjectKind]) -> str:
    """An SQL list of an enum's values."""
    return ", ".join(f"'{member.value}'" for member in values)


class DecisionRow(ModelBase):
    """One consulted decision: what it was about, the facts, the answer, the outcome."""

    __tablename__ = "agent_decisions"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_agent_decisions"),
        CheckConstraint(f"point {POINT_FORM}", name="point_form"),
        CheckConstraint("version >= 1 AND (revision IS NULL OR revision >= 1)", name="versions"),
        CheckConstraint(f"subject_kind IN ({known(SubjectKind)})", name="subject_known"),
        CheckConstraint("part >= 0 AND latency_ms >= 0", name="counts"),
        CheckConstraint(f"language {LANGUAGE_FORM}", name="language_form"),
        CheckConstraint(
            f"rule_outcome {CODE_FORM} AND outcome {CODE_FORM}"
            " AND length(rule_outcome) <= 640 AND length(outcome) <= 640",
            name="outcome_form",
        ),
        CheckConstraint(f"reason IN ({known(DecisionReason)})", name="reason_known"),
        CheckConstraint(f"source IN ({known(DecisionSource)})", name="source_known"),
        CheckConstraint(
            "state_hash IS NULL OR octet_length(state_hash) = 16", name="state_hash_length"
        ),
        Index("ix_agent_decisions_point", "point", "created_at"),
        {"postgresql_partition_by": monthly_partition_range("created_at")},
    )

    id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    point: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(SmallInteger)
    # Ревизия порогов; None — решение без порогов (запасной исход до ответа Jev).
    revision: Mapped[int | None] = mapped_column(Integer)
    shadow: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    subject_kind: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[UUID] = mapped_column(Uuid)
    part: Mapped[int] = mapped_column(Integer, server_default="0")
    language: Mapped[str] = mapped_column(Text)
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB)
    state_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    probabilities: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=sql_text("'{}'::jsonb")
    )
    rule_outcome: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)
    jev_snapshot: Mapped[str | None] = mapped_column(Text)
    jev_request_id: Mapped[str | None] = mapped_column(Text)


class DecisionOutcomeRow(ModelBase):
    """What followed a decided subject, in the point's closed form."""

    __tablename__ = "agent_decision_outcomes"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at", name="pk_agent_decision_outcomes"),
        CheckConstraint(f"point {POINT_FORM}", name="point_form"),
        CheckConstraint(f"subject_kind IN ({known(SubjectKind)})", name="subject_known"),
        CheckConstraint("part >= 0", name="part_counted"),
        Index("ix_agent_decision_outcomes_subject", "subject_id"),
        {"postgresql_partition_by": monthly_partition_range("created_at")},
    )

    id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    point: Mapped[str] = mapped_column(Text)
    subject_kind: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[UUID] = mapped_column(Uuid)
    part: Mapped[int] = mapped_column(Integer, server_default="0")
    observation: Mapped[dict[str, Any]] = mapped_column(JSONB)


class PolicyStateRow(ModelBase):
    """A policy version's state in force and the threshold revision it uses (EU home)."""

    __tablename__ = "decision_policies"
    __table_args__ = (
        PrimaryKeyConstraint("point", "version", name="pk_decision_policies"),
        CheckConstraint(f"point {POINT_FORM}", name="point_form"),
        CheckConstraint(f"state IN ({STATES})", name="state_known"),
        CheckConstraint("version >= 1 AND revision >= 1", name="versions"),
        CheckConstraint("questions_digest ~ '^[0-9a-f]{16}$'", name="digest_form"),
        CheckConstraint("note IS NULL OR length(note) <= 500", name="note_length"),
        # Версия в силе — только с существующей ревизией порогов.
        ForeignKeyConstraint(
            ["point", "version", "revision"],
            [
                "decision_thresholds.point",
                "decision_thresholds.version",
                "decision_thresholds.revision",
            ],
        ),
        # Одна действующая и одна теневая версия на точку — это держит база, не код.
        Index(
            "uq_decision_policies_active",
            "point",
            unique=True,
            postgresql_where=sql_text("state = 'active'"),
        ),
        Index(
            "uq_decision_policies_shadow",
            "point",
            unique=True,
            postgresql_where=sql_text("state = 'shadow'"),
        ),
        {"info": table_info(homes=(Home.EU,))},
    )

    point: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(SmallInteger)
    state: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer)
    # Хеш формулировок вопросов: образ с другими формулировками не возьмёт эти пороги.
    questions_digest: Mapped[str] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(Text)


class ThresholdRevisionRow(ModelBase):
    """A fitted revision of a policy version's cuts, with its calibration report (EU home)."""

    __tablename__ = "decision_thresholds"
    __table_args__ = (
        PrimaryKeyConstraint("point", "version", "revision", name="pk_decision_thresholds"),
        CheckConstraint(f"point {POINT_FORM}", name="point_form"),
        CheckConstraint("version >= 1 AND revision >= 1", name="versions"),
        CheckConstraint("questions_digest ~ '^[0-9a-f]{16}$'", name="digest_form"),
        CheckConstraint("jsonb_typeof(cuts) = 'object'", name="cuts_object"),
        {"info": table_info(homes=(Home.EU,))},
    )

    point: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(SmallInteger)
    revision: Mapped[int] = mapped_column(Integer)
    questions_digest: Mapped[str] = mapped_column(Text)
    # Края полосы неуверенности каждого порога: {"matches": {"lower": .., "upper": ..}}.
    cuts: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Отчёт калибровки: только числа — счёт, ECE, точность по языкам, сверка с эталоном.
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    passed: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


DECISION_MODELS: Final = (DecisionRow, DecisionOutcomeRow, PolicyStateRow, ThresholdRevisionRow)
