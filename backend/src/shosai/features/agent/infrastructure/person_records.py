"""Settings > Leo, a person's installed skills, their ratings and their donated cases (§3.4).

Personal by nature, like the threads. A missing settings row means the defaults: everything
on, `auto` model and language, balanced answers. A skill is pinned to the commit it was read
at and keeps its body, as the draft did. A rating belongs to one answer and goes with its
thread; an evaluation case exists only with the person's consent and goes with its rating,
the consent, the thread or the account, and after a year (ADR 0068 AG-D13).
"""

from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shosai.core.db.model_base import ModelBase

LENGTHS: Final = "'concise', 'balanced', 'detailed'"
RATINGS: Final = "'useful', 'not_useful'"
SKILL_SOURCES: Final = "'github', 'skills_sh'"


class AgentSettingsRecord(ModelBase):
    """A person's Settings > Leo; absent while they keep the defaults."""

    __tablename__ = "agent_settings"
    __table_args__ = (
        CheckConstraint("char_length(leo_model) BETWEEN 1 AND 200", name="leo_model_length"),
        CheckConstraint(
            "char_length(response_language) BETWEEN 2 AND 10", name="response_language_length"
        ),
        CheckConstraint(f"response_length IN ({LENGTHS})", name="response_length_known"),
    )

    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    leo_model: Mapped[str] = mapped_column(Text, server_default="auto")
    response_language: Mapped[str] = mapped_column(Text, server_default="auto")
    response_length: Mapped[str] = mapped_column(Text, server_default="balanced")
    web_search: Mapped[bool] = mapped_column(Boolean, server_default=true())
    voice_mode: Mapped[bool] = mapped_column(Boolean, server_default=true())
    knowledge_base_search: Mapped[bool] = mapped_column(Boolean, server_default=true())
    connected_services_search: Mapped[bool] = mapped_column(Boolean, server_default=true())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentSkillRecord(ModelBase):
    """A SKILL.md the person installed, pinned to the commit it was read at."""

    __tablename__ = "agent_skills"
    __table_args__ = (
        CheckConstraint(f"source IN ({SKILL_SOURCES})", name="source_known"),
        CheckConstraint("char_length(repo) BETWEEN 3 AND 140", name="repo_length"),
        CheckConstraint("char_length(skill_path) <= 255", name="skill_path_length"),
        CheckConstraint("char_length(ref) BETWEEN 1 AND 80", name="ref_length"),
        CheckConstraint("char_length(slug) BETWEEN 1 AND 80", name="slug_length"),
        CheckConstraint("char_length(body) BETWEEN 1 AND 24100", name="body_length"),
        UniqueConstraint("user_id", "repo", "skill_path", name="uq_agent_skills_user_repo_path"),
        Index("ix_agent_skills_user", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    source: Mapped[str] = mapped_column(Text)
    repo: Mapped[str] = mapped_column(Text)
    # Папка SKILL.md в репозитории; пусто — корень.
    skill_path: Mapped[str] = mapped_column(Text, server_default="")
    # Коммит, к которому навык закреплён.
    ref: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    body: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, server_default="")
    installs: Mapped[int | None] = mapped_column(Integer)
    has_extra_files: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentFeedbackRecord(ModelBase):
    """The person's rating of one answer."""

    __tablename__ = "agent_feedback"
    __table_args__ = (
        CheckConstraint(f"rating IN ({RATINGS})", name="rating_known"),
        Index("ix_agent_feedback_thread", "thread_id"),
    )

    message_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    thread_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_threads.id", ondelete="CASCADE")
    )
    run_id: Mapped[UUID | None] = mapped_column(Uuid)
    rating: Mapped[str] = mapped_column(Text)
    # Стал ли ход оценочным случаем (согласие и ни одного источника из workspace).
    shared: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentEvalCaseRecord(ModelBase):
    """A rated turn the person allowed to help improve Leo, as the model saw it."""

    __tablename__ = "agent_eval_cases"
    __table_args__ = (
        CheckConstraint(f"rating IN ({RATINGS})", name="rating_known"),
        UniqueConstraint("message_id", name="uq_agent_eval_cases_message_id"),
        Index("ix_agent_eval_cases_user", "user_id"),
        Index("ix_agent_eval_cases_created", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    message_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_feedback.message_id", ondelete="CASCADE")
    )
    thread_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_threads.id", ondelete="CASCADE")
    )
    rating: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text)
    # Ход так, как его видела модель: вопрос, дайджесты, источники, ответ; имя замаскировано.
    case: Mapped[dict[str, Any]] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[str | None] = mapped_column(Text)
    toolsets: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    prompt_version: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


PERSON_MODELS: Final = (
    AgentSettingsRecord,
    AgentSkillRecord,
    AgentFeedbackRecord,
    AgentEvalCaseRecord,
)
