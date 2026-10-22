# Team chats API

The contract between the cabinet's team-chat screens and the backend's `chats` slice: §1 of the
[chats plan](../../docs/plan/slices/chats.md), approved with [ADR 0063](../../docs/adr/0063-team-chats-contract-and-screens.md)
for the scope of [ADR 0062](../../docs/adr/0062-team-chats-through-leo-on-demand.md). Until `chats` serves them,
`npm run dev` answers exactly these routes from `src/features/chats/mocks/` (the messenger links from
`src/features/identity/mocks/messenger-links.ts`, the digest's task proposals from `src/features/leo/mocks/`); the
slice then points `api/` at the generated client and deletes the mocks. The shapes are in
`src/features/chats/domain/{contract,telegram-contract,slack-contract,digest-contract}.ts` and
`src/features/identity/domain/messenger-links-contract.ts`; refusals are the platform's envelope
`{error: {code, request_id, params?}}` (ADR 0008), worded by the cabinet from `domain/problems.ts`. Snake_case;
calendar days are `"2026-10-22"`.

Every `/v1/workspaces/{id}/chats*` route answers 404 `workspace_not_found` to someone who is not a member and 423
`workspace_suspended` while the workspace is suspended (the workspaces gate); members read, owners and admins change
(403 `not_workspace_admin`).

## Connections and settings

| Method   | Path                                          | Body                                              | Response                |
| -------- | --------------------------------------------- | ------------------------------------------------- | ----------------------- |
| `GET`    | `/v1/workspaces/{id}/chats/settings`          | —                                                 | `ChatSettings`          |
| `PATCH`  | `/v1/workspaces/{id}/chats/settings`          | `{retention_days: 30 \| 90 \| 365}`               | `ChatSettings`          |
| `GET`    | `/v1/workspaces/{id}/chats`                   | —                                                 | `ChatConnectionsPage`   |
| `GET`    | `/v1/workspaces/{id}/chats/{chat_id}`         | —                                                 | `ChatConnection`        |
| `PATCH`  | `/v1/workspaces/{id}/chats/{chat_id}`         | `{project_id?, mode?, data_notice_accepted?}`     | `ChatConnection`        |
| `DELETE` | `/v1/workspaces/{id}/chats/{chat_id}`         | —                                                 | `204`                   |
| `POST`   | `/v1/workspaces/{id}/chats/{chat_id}/rejoin`  | —                                                 | `ChatConnection`        |

The list puts the chats that need attention first, then the most recently active. A change to the mode `all`
needs `data_notice_accepted: true`; on Telegram it leaves the chat with `rights_missing` until the bot is an admin
of the group (CF-D1). Disconnecting erases the chat's stored messages and digests.

## Telegram

| Method   | Path                                                         | Body                                                    | Response           |
| -------- | ------------------------------------------------------------ | ------------------------------------------------------- | ------------------ |
| `POST`   | `/v1/workspaces/{id}/chats/telegram/connect-codes`           | `{project_id, mode, data_notice_accepted, connection_id?}` | `201 ConnectCode` |
| `GET`    | `/v1/workspaces/{id}/chats/telegram/connect-codes/{code_id}` | —                                                       | `ConnectStatus`    |
| `DELETE` | `/v1/workspaces/{id}/chats/telegram/connect-codes/{code_id}` | —                                                       | `204`              |

The screen polls the code every 2 s while it is open. In the mocks a pending code connects on its first poll after
3 s to the next sample group; the session-storage key `chats-demo` set to `expire`, `refuse` or `member` makes new
codes expire, be refused (`chat_already_connected`) or connect the bot without admin rights.

## Slack

| Method   | Path                                                                   | Body                                              | Response               |
| -------- | ---------------------------------------------------------------------- | ------------------------------------------------- | ---------------------- |
| `GET`    | `/v1/workspaces/{id}/chats/slack/installations`                        | —                                                 | `{items: SlackInstallation[]}` |
| `POST`   | `/v1/workspaces/{id}/chats/slack/installations`                        | `{installation_id?}`                              | `201 SlackHandoff`     |
| `DELETE` | `/v1/workspaces/{id}/chats/slack/installations/{installation_id}`      | —                                                 | `204`                  |
| `GET`    | `/v1/workspaces/{id}/chats/slack/installations/{installation_id}/channels` | `?q=&cursor=&limit=`                          | `SlackChannelsPage`    |
| `POST`   | `/v1/workspaces/{id}/chats/slack`                                      | `{installation_id, channels, mode, data_notice_accepted}` | `201 {items: ChatConnection[]}` |

The handoff opens `authorize_url` in a popup; the provider returns to connectors' callback, which sends the popup to
`/oauth/callback?flow=chats&status=connected&installation_id=…` (or `status=denied`, `status=error&error=<code>`).
In the mocks the consent is the demo page `/oauth/demo-authorize?flow=chats`, and
`/v1/integrations/oauth/slack/callback` stands in for connectors.

## Leo's digest

| Method | Path                                                                         | Body          | Response          |
| ------ | ---------------------------------------------------------------------------- | ------------- | ----------------- |
| `GET`  | `/v1/workspaces/{id}/chats/{chat_id}/digests/{digest_id}`                    | —             | `ChatDigest`      |
| `POST` | `/v1/workspaces/{id}/chats/{chat_id}/digests/{digest_id}/task-proposals`     | `{item_ids}`  | `201 LeoProposal` |

Leo's stream carries the digest as `{type: "artifact", artifact: {kind: "chat_digest", ref, alt, workspace_id,
chat_id}}` (CF-D11); the card reads it by `ref`. "Make a task" puts one `tasks.create` approval card into the
conversation (CF-D5); once approved, the items carry `task_id` and the tasks carry the `chat` source (tasks TK-D13).
In the demo, ask Leo to "go through #release for the week" (or name `support`, `pricing` or `weekend` for the other
states).

## Messenger links (identity)

| Method   | Path                                                       | Body | Response                  |
| -------- | ---------------------------------------------------------- | ---- | ------------------------- |
| `GET`    | `/v1/me/messenger-links`                                   | —    | `MessengerLinksResponse`  |
| `POST`   | `/v1/me/messenger-links/hint-dismissal`                    | —    | `204`                     |
| `POST`   | `/v1/me/messenger-links/telegram`                          | —    | `201 LinkRequest`         |
| `GET`    | `/v1/me/messenger-links/telegram/requests/{request_id}`    | —    | `LinkRequest`             |
| `POST`   | `/v1/me/messenger-links/{link_id}/confirm`                 | —    | `MessengerLink`           |
| `DELETE` | `/v1/me/messenger-links/{link_id}`                         | —    | `204`                     |

A Slack account matched by email arrives as `proposed` and acts only once the person confirms it (CF-D4);
`hint_dismissed` closes the workspace hint for the person for good (CF-D9). In the mocks a link request links on its
first poll after 3 s; `chats-demo` = `expire` or `refuse` (`messenger_account_taken`) changes that.
