"""Meeting surroundings of the `lead` persona: folders, result share links, templates, integrations.

The link tokens come from ids.json: the draft stores them in plain text, and the
recording visits open the public page at a known address.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from meetassist.features.meetings.infrastructure.share_comment_models import MeetingShareComment
from meetassist.features.meetings.infrastructure.share_models import MeetingResultShare
from meetassist.models.meeting_folder import MeetingFolder
from meetassist.models.meeting_integration import MeetingIntegration
from meetassist.models.meeting_template import MeetingTemplate
from meetassist.models.session import Session
from meetassist.models.user import User
from meetassist.services.auth_service import hash_password
from sqlalchemy.ext.asyncio import AsyncSession

import meeting_content as content
from stable_ids import SHARE_PASSWORD, SHARES

#: Папки: ключ, имя, иконка, цвет (пресеты черновика), родитель, избранная.
_FOLDERS = (
    ("work", "Работа", "layers", "#7C5CFF", None, False),
    ("legal", "Юридическое", "shield", "#1D8C3E", "work", False),
    ("contracts", "Договоры", "book", "#E1261C", "legal", False),
    ("finance", "Финансы", "trend", "#2563EB", None, True),
    ("hiring", "Найм", "user", "#E8893B", None, False),
)

#: Встреча → папка.
_FOLDER_OF = {"budget": "finance", "lawyer": "contracts", "kickoff": "work"}

_TEMPLATES = (
    ("1:1 с руководителем", ("Что обсудили", "Договорённости", "Вопросы на следующую встречу")),
    ("Звонок с клиентом", ("Контекст", "Боли клиента", "Следующие шаги")),
)


async def seed_workspace(db: AsyncSession, owner: User, clock: datetime, sessions: dict[str, Session]) -> None:
    """Seed the owner's meeting surroundings."""
    await _folders(db, owner, clock, sessions)
    await _shares(db, owner, clock, sessions)
    for index, (name, sections) in enumerate(_TEMPLATES):
        db.add(
            MeetingTemplate(
                user_id=owner.id,
                name=name,
                sections=[{"id": f"s{order}", "title": title, "order": order} for order, title in enumerate(sections)],
                created_at=clock - timedelta(days=30 - index),
            )
        )
    # Интеграции: Notion с выбранной страницей и Slack. Остальные семь — не
    # подключены (строк нет). Хранилищам строк не даём: без зеркала коннектора
    # черновик показал бы «нужно переподключить».
    db.add(MeetingIntegration(user_id=owner.id, type="notion", credential_ciphertext=b"parity-seed",
                              target="1f2e3d4c5b6a49788796a5b4c3d2e1f0", account_label="Whisperer Workspace",
                              push_notes=True, push_action_items=False, created_at=clock - timedelta(days=20)))
    db.add(MeetingIntegration(user_id=owner.id, type="slack", credential_ciphertext=b"parity-seed",
                              account_label="#meetings", created_at=clock - timedelta(days=19)))
    await db.flush()


async def _folders(db: AsyncSession, owner: User, clock: datetime, sessions: dict[str, Session]) -> None:
    folders: dict[str, MeetingFolder] = {}
    for position, (key, name, icon, color, parent, favorite) in enumerate(_FOLDERS):
        folder = MeetingFolder(user_id=owner.id, name=name, icon=icon, color=color, favorite=favorite,
                               parent_id=None if parent is None else folders[parent].id, position=position,
                               created_at=clock - timedelta(days=60 - position))
        db.add(folder)
        await db.flush()
        folders[key] = folder
    for meeting, folder in _FOLDER_OF.items():
        sessions[meeting].folder_id = folders[folder].id


async def _shares(db: AsyncSession, owner: User, clock: datetime, sessions: dict[str, Session]) -> None:
    """Public with comments, password-protected, with comments closed, and expired.
    A revoked link is the absence of a row: its token never reaches the database."""
    public = _share(owner, sessions["budget"], SHARES["public"], "public", clock)
    locked = _share(owner, sessions["lawyer"], SHARES["locked"], "shared", clock)
    locked.password_hash = hash_password(SHARE_PASSWORD)
    locked.expires_at = clock + timedelta(days=30)
    closed = _share(owner, sessions["kickoff"], SHARES["closed"], "public", clock)
    closed.comments_enabled = False
    expired = _share(owner, sessions["report"], SHARES["expired"], "public", clock)
    expired.expires_at = clock - timedelta(days=1)
    db.add_all([public, locked, closed, expired])
    await db.flush()
    for share, comments in ((public, content.BUDGET_COMMENTS), (closed, content.KICKOFF_COMMENTS)):
        for index, (author, body) in enumerate(comments):
            db.add(MeetingShareComment(share_id=share.id, author_name=author, body=body,
                                       created_at=clock - timedelta(hours=3) + timedelta(minutes=37 * index)))


def _share(owner: User, session: Session, token: str, visibility: str, clock: datetime) -> MeetingResultShare:
    return MeetingResultShare(session_id=session.id, owner_id=owner.id, token=token, visibility=visibility,
                              include_transcript=True, include_speakers=True, comments_enabled=True,
                              created_at=clock - timedelta(hours=6))
