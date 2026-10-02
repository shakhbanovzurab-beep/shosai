"""MCP of the `lead` persona: its own server for external AIs and external MCP servers for Leo.

The draft stores the server token as a hash and shows a mask derived from the hash: the
plain token is set in ids.json so that the mask does not change from seed to seed. The
external servers are one per health state the draft derives from the failure counter:
working (OAuth), failing, unreachable and not checked yet.

The OAuth client is the registered (DCR) client "Claude": the consent screen finds it by
`client_id` without a network call.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from meetassist.models.mcp import McpClientConnection, McpExposedResource, McpRegisteredClient, McpToken
from meetassist.models.user import User
from meetassist.services.mcp import hash_token
from sqlalchemy.ext.asyncio import AsyncSession

from stable_ids import MCP_CLIENT_ID, MCP_REDIRECT_URI, MCP_SCOPES, MCP_TOKEN

#: Внешние серверы: имя, адрес, вид авторизации, минут назад ответил, сбоев подряд, код ошибки.
_CLIENTS = (
    ("Notion MCP", "https://mcp.notion.com/mcp", "oauth2", 60, 0, None),
    ("Linear", "https://mcp.linear.app/mcp", "bearer", 90, 2, "unreachable"),
    ("Sentry", "https://mcp.sentry.dev/mcp", "bearer", None, 5, "unreachable"),
    ("Docs MCP", "https://docs.example.com/mcp", "none", None, 0, None),
)


async def seed_mcp(db: AsyncSession, owner: User, clock: datetime) -> None:
    """Seed the owner's MCP server, their external servers and the OAuth client."""
    db.add(McpToken(user_id=owner.id, token_hash=hash_token(MCP_TOKEN), kind="personal", expires_at=None,
                    created_at=clock - timedelta(days=20)))
    # Стенограммы скрыты владельцем, задачи скрыты по умолчанию черновика.
    db.add_all([
        McpExposedResource(user_id=owner.id, key="transcripts", enabled=False),
        McpExposedResource(user_id=owner.id, key="action_items", enabled=False),
    ])
    for index, (name, url, auth_kind, ok_minutes_ago, failures, error_code) in enumerate(_CLIENTS):
        last_ok = None if ok_minutes_ago is None else clock - timedelta(minutes=ok_minutes_ago)
        last_error = clock - timedelta(minutes=30) if failures > 0 else None
        db.add(McpClientConnection(
            user_id=owner.id, name=name, url=url, auth_kind=auth_kind,
            oauth_issuer="https://mcp.notion.com" if auth_kind == "oauth2" else None,
            last_ok_at=last_ok, last_error_at=last_error, last_error_code=error_code, consecutive_failures=failures,
            created_at=clock - timedelta(days=15) + timedelta(seconds=index),
        ))
    db.add(McpRegisteredClient(client_id=MCP_CLIENT_ID, client_name="Claude", redirect_uris=MCP_REDIRECT_URI,
                               scope=" ".join(MCP_SCOPES), created_at=clock - timedelta(days=3)))
    await db.flush()
