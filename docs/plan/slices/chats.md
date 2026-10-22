# chats — slice plan

Slice card: [SLICE_MAP.md §4.2.27](../SLICE_MAP.md#27-chats). Decision: [ADR 0062](../../adr/0062-team-chats-through-leo-on-demand.md). Frontend package: [CHATS-frontend](../packages/CHATS-frontend.md) (prompt [CHATS-frontend.md](../prompts/CHATS-frontend.md)). Status: [STATUS.md](../STATUS.md), rows `chats` and `chats-frontend`.

This file starts with the contract the cabinet's screens are built on. The rest of the plan — data, flows, the bot and webhook handling, Leo's tools, steps — is written by the backend slice's planning session ([S-feature-slice.md](../prompts/S-feature-slice.md)), which keeps this contract as fixed: a change needs the owner.

---

## 1. Contract (decided with the frontend, 2026-10-22)

- **Status:** the scope is **the owner's, of 2026-10-22** (ADR 0062, the prompt's "Scope decided by the owner"). The contract was proposed by the agent of the CHATS-frontend planning session and **approved by the owner on 2026-10-22** with the package plan's decisions CF-D1…CF-D11 ([ADR 0063](../../adr/0063-team-chats-contract-and-screens.md)): all as proposed but CF-D9, which the owner changed (the hint's dismissal is the account's, §1.2).
- **Conventions** (as tasks §3.8): `/v1/...`, snake_case, ADR 0008 errors `{error: {code, request_id, params?, fields?}, detail}` with codes the cabinet words in 16 languages, `{items, next_cursor}` pages with opaque cursors and `limit` 1–100 (default 50) unless a route declares other bounds, optional `Idempotency-Key` on unsafe writes a client may retry, moments as RFC 3339 UTC, days as `YYYY-MM-DD`.
- **Who:** "admin" means a workspace's owner or admin; "member" any member. A person who is not a member of the workspace gets 404 on every `/v1/workspaces/{id}/chats*` route; a suspended workspace answers 423 (workspaces' gate). Members read; only admins change anything (ADR 0062 point 2).
- **The cabinet's mocks answer exactly this** (the package's step 1), so the backend slice only replaces the data source.

### 1.1 Shapes

```
Messenger      = telegram | slack
Mode           = mentions        ("Only messages to Leo": Shosai keeps only messages addressed to Leo)
               | all             ("Every message, for digests": Shosai keeps every message of the chat)
Binding        = {kind: "workspace"} | {kind: "project", project: {id, name}}
ChatProblem    = bot_not_in_chat  (Telegram: the bot left or was removed; Slack: Leo is not in the channel)
               | rights_missing   (Telegram, mode all: the bot is not an administrator of the group, CF-D1)
               | token_expired    (Slack: the installation's token was revoked or the app removed)

ChatConnection = {id, workspace_id, messenger, title (the chat's name as the messenger reports it),
                  kind: group | supergroup (Telegram) | public_channel | private_channel (Slack),
                  binding: Binding, mode: Mode,
                  state: working | needs_attention, problem: ChatProblem | null (set exactly when needs_attention),
                  last_activity_at: datetime | null (the last message Shosai received from the chat),
                  history_from: datetime (the moment Shosai's record of the chat starts: the bot's joining,
                                          or the connection for Slack, CF-D3),
                  stored: {messages: int, oldest_at: datetime | null} (what a disconnection erases),
                  connected_at, connected_by: {user_id, name},
                  slack: {installation_id, channel_id} | null}

ChatSettings   = {retention_days: 30 | 90 | 365, home: "ru" | "eu" (the workspace's data home),
                  messengers: [{messenger: "telegram", bot_username} | {messenger: "slack", app_name}]
                    (only the messengers this deployment serves; a missing one is not offered),
                  limits: {connections: 50}}

ConnectCode    = {id, code (8 characters of A–Z and 2–9 without 0, O, 1, I; shown as "K7QM-4PZX",
                             sent without the hyphen), expires_at (30 min),
                  bot_username, mode, binding: Binding,
                  add_url ("https://t.me/<bot>?startgroup=<code>"),
                  add_as_admin_url ("https://t.me/<bot>?startgroup=<code>&admin=<rights>", for mode all, CF-D1:
                                    the smallest value Telegram accepts, confirmed on a live bot by this
                                    slice; the admin may switch every right off, the bot still gets
                                    every message),
                  command ("/connect@<bot> <code>", for adding the bot by hand),
                  connection_id: string | null (a reconnect code for an existing connection)}
ConnectStatus  = {status: pending | connected | expired | refused,
                  connection: ChatConnection | null (when connected),
                  refusal: chat_already_connected | not_a_group | wrong_chat | connections_full | null}

SlackInstallation = {id, team: {id, name, icon_url | null}, installed_at, installed_by: {user_id, name},
                     state: working | token_expired, connections: int}
SlackChannel   = {id, name, private, member_count: int | null, leo_in_channel, connection_id: string | null}
                 (public channels, and private channels Leo is already in)

MessengerLink  = {id, messenger, account: {handle: string | null ("@mara" in Telegram, "@mara" in Slack),
                                           name (the messenger's display name)},
                  space: {id, name} | null (the Slack workspace; null for Telegram),
                  state: linked | proposed (a Slack match by email waiting for the person, CF-D4),
                  linked_at: datetime | null, proposed_at: datetime | null}
LinkRequest    = {id, url ("https://t.me/<bot>?start=<token>"), expires_at (10 min),
                  status: pending | linked | expired | refused, link: MessengerLink | null,
                  refusal: messenger_account_taken | null}

ChatMessageRef = {id, author_name, sent_at, quote (the message's text, cut to 280 characters),
                  url: string | null (Telegram: t.me/c/<chat>/<message> for a supergroup, null for a basic
                                      group, which has no message links; Slack: the message's permalink)}
DigestItem     = {id, text (Leo's words in the person's answer language, ≤ 300), message: ChatMessageRef,
                  proposal_id: string | null (the approval card made from it, if any),
                  task_id: string | null (the task that card created; added by the package's step 1,
                                          agent-derived and additive, so "Task created" can open it, §3.8)}
DigestPromise  = DigestItem & {who: {user_id: string | null (a matched member), name}, due_on: date | null,
                               when_text: string | null (the time as it was said, when it is not a day)}
ChatDigest     = {id, chat: {id, workspace_id, messenger, title, binding: Binding}, period: {from, to},
                  created_at, coverage: {history_from, messages_read: int, truncated (more than 5 000
                  messages in the period: the latest 5 000 were read)},
                  decisions: DigestItem[] (≤ 30), questions: DigestItem[] (≤ 30),
                  promises: DigestPromise[] (≤ 30)}
```

### 1.2 Routes

| Route | Who | Notes |
|---|---|---|
| `GET /v1/workspaces/{id}/chats/settings` | member | `ChatSettings` |
| `PATCH /v1/workspaces/{id}/chats/settings` | admin | `{retention_days}` → `ChatSettings`; a shorter period erases older messages at the next sweep (CF-D8) |
| `GET /v1/workspaces/{id}/chats` | member | page of `ChatConnection`: those needing attention first, then by `last_activity_at`, newest first, never-active last; ≤ 50 per workspace, so one page in practice |
| `GET /v1/workspaces/{id}/chats/{chat_id}` | member | `ChatConnection`; 404 `chat_not_found` |
| `PATCH /v1/workspaces/{id}/chats/{chat_id}` | admin | `{project_id?: string \| null, mode?, data_notice_accepted?}` → `ChatConnection`. A change to `all` needs `data_notice_accepted: true` (422 `data_notice_required`); on Telegram it leaves the chat `needs_attention` with `rights_missing` until the bot is an administrator (CF-D1). An unknown project 422 `project_not_found` |
| `DELETE /v1/workspaces/{id}/chats/{chat_id}` | admin | 204: the chat's stored messages and digests are erased in the same transaction, the bot leaves the chat; tasks made from it keep their source line and message link (TK-D13) |
| `POST /v1/workspaces/{id}/chats/{chat_id}/rejoin` | admin | Slack public channel with `bot_not_in_chat`: Leo joins it again → `ChatConnection`; another chat 409 `rejoin_unsupported` |
| `POST /v1/workspaces/{id}/chats/telegram/connect-codes` | admin | `{project_id: string \| null, mode, data_notice_accepted: true, connection_id?}` → 201 `ConnectCode`; a new code voids the person's earlier pending code in this workspace; with `connection_id` it reconnects that chat (`bot_not_in_chat`, `rights_missing`) and another group's answer is refused `wrong_chat`. 409 `connections_full` at 50; 422 `data_notice_required` |
| `GET /v1/workspaces/{id}/chats/telegram/connect-codes/{code_id}` | the code's creator | `ConnectStatus`; the cabinet polls it while the dialog shows the code (its shared polling resource, every 1.5 s) and cancels a pending code nobody watches any more |
| `DELETE /v1/workspaces/{id}/chats/telegram/connect-codes/{code_id}` | the code's creator | 204; the code stops working |
| `POST /v1/workspaces/{id}/chats/slack/installations` | admin | `{installation_id?}` → 201 `{authorize_url, expires_at}`: the OAuth handoff (connectors issues the state and owns the callback, ADR 0062). The popup returns to the cabinet's `/oauth/callback?flow=chats&status=connected&installation_id=…` or `status=denied` / `status=error&error=<code>`, which posts the result to the opener (the existing connectors pattern). With `installation_id` it re-authorises that installation (`token_expired`) |
| `GET /v1/workspaces/{id}/chats/slack/installations` | member | `{items: SlackInstallation[]}` (≤ 10, no cursor) |
| `DELETE /v1/workspaces/{id}/chats/slack/installations/{installation_id}` | admin | 204: the token is revoked and every chat of the installation is disconnected as by `DELETE …/chats/{chat_id}` |
| `GET /v1/workspaces/{id}/chats/slack/installations/{installation_id}/channels` | admin | `?q=` (name contains), page of `SlackChannel`, by name; 409 `token_expired` |
| `POST /v1/workspaces/{id}/chats/slack` | admin | `{installation_id, channels: [{channel_id, project_id: string \| null}] (1–20), mode, data_notice_accepted: true}` → 201 `{items: ChatConnection[]}`; all or nothing: 409 `channel_already_connected` with `params.channel_ids`, 409 `connections_full`; a private channel Leo is not in is refused with `leo_not_in_channel`. Shosai joins the public ones itself |
| `GET /v1/workspaces/{id}/chats/{chat_id}/digests/{digest_id}` | the person who asked for it, while a member | `ChatDigest`; kept 30 days and erased with the chat's disconnection or its messages' retention: 404 `digest_not_found` |
| `POST /v1/workspaces/{id}/chats/{chat_id}/digests/{digest_id}/task-proposals` | the person who asked for the digest | `{item_ids}` (1–20, decisions, questions or promises) → 201 `LeoProposal` (the cabinet's `/v1/agent/actions` shape): one `tasks.create` with a task per item, planned through agent's Action Gateway in the digest's thread, without a model round (CF-D5); each task in the chat's workspace and its binding's project, titled from the item, a promise's matched member as assignee and its day as due; the items record `proposal_id`, and the executed card records each item's `task_id`. An item in a pending proposal or already made a task 409 `item_already_proposed` |
| `GET /v1/me/messenger-links` | the person | `{items: MessengerLink[], hint_dismissed: bool}`: linked and proposed accounts (identity, below), and whether the person closed the workspace hint for linking (CF-D9) |
| `POST /v1/me/messenger-links/hint-dismissal` | the person | 204; the hint never shows again for this account, in any workspace or on any device (CF-D9, the owner's change); a repeat changes nothing |
| `POST /v1/me/messenger-links/telegram` | the person | → 201 `LinkRequest`; 409 `messenger_already_linked` |
| `GET /v1/me/messenger-links/telegram/requests/{request_id}` | the person | `LinkRequest`; the cabinet polls it every 2 s while the tab is visible and once when the tab comes back |
| `POST /v1/me/messenger-links/{link_id}/confirm` | the person | a proposed Slack link → `MessengerLink` linked (CF-D4); a linked one is returned as is |
| `DELETE /v1/me/messenger-links/{link_id}` | the person | 204: unlink, or "Not me" for a proposal (that Slack account is not proposed again) |

Other codes: `chat_not_found`, `installation_not_found`, `code_not_found`, `request_not_found`, `link_not_found`, `item_not_found`, `retention_invalid`, `mode_invalid`, `not_workspace_admin` (403 for a member's change).

**The messenger link is identity's** (`/v1/me*`; [identity plan](identity.md), step 18): one Telegram account per Shosai account and one Shosai account per Telegram account; Slack accounts per Slack workspace (CF-D10). A Slack member whose Slack email equals their Shosai account's email, and who is a member of the connected workspace, gets a `proposed` link the first time they write to Leo; it acts only once confirmed (CF-D4), and until then Leo's reply is `chats.reply.confirm_slack` with the link to confirm (§1.5). The hint's dismissal (CF-D9) is identity's too: a setting of the account, exported and erased with it. A person whose Slack email differs has no Slack link in this contract (open, §2 of the package plan).

### 1.3 Leo's digest

- **The tool** `chats.digest` (toolset `chats`, read) takes `{chat (a connection id or a chat's name in the thread's workspace), from, to}` (≤ 31 days). Its result for the model is the digest's items as text with their counts and `coverage`, labelled with a new provenance `chat:foreign` (Leo §7.4, added by the backend slice; message text is foreign text, ADR 0062 point 5). A chat in mode `mentions` answers the error code `chat_mentions_only`, which Leo explains in words; no card.
- **The stream** carries the digest as Leo's artifact (CF-D11), additive to §13.2's `artifact` event: `artifact {kind: "chat_digest", ref: <digest_id>, alt, workspace_id, chat_id}`, and the thread's history returns it in the message's artifacts. The cabinet reads the digest by `GET …/digests/{digest_id}` and renders the card; "Make a task" calls `…/task-proposals` and the approval card appears in the same message.
- **States the card shows:** the period starts before `history_from` (Telegram gives Shosai only messages written after the bot joined, ADR 0062 point 5); no messages in the period; messages but nothing found; `truncated`; the digest gone (404).

### 1.4 The task's `chat` source

Written in the [tasks plan](tasks.md) as **TK-D13** (§3.10 there): `TaskSource.kind` gains `chat` with `chat: {connection_id | null, messenger, chat_title, message: {url | null, sent_at}}`, and `Card` gains `source_chat: {messenger, chat_title} | null`.

### 1.5 What Leo answers in the chat

Leo's replies in a messenger are text in the chat, not a cabinet screen. The replies inside a run (task created, need clarification, no rights) are written by the model under the instructions below: model-facing text, English only (CLAUDE.md "Prompts and model-facing text"), registered in the backend's model-facing test when the slice adds them; the language of the reply is stated in the prompt, never chosen by a branch of code. By CF-D6 (approved), the replies that come **before** any run — the sender is not linked, not a member, or the chat is connected to no workspace — are sent without a model, as the server's own text worded through i18n in the sender's messenger language (Telegram `User.language_code`, Slack's user locale), English when it is none of the 16; their English source closes this section.

**Common instruction (every reply in a chat):**

```text
You are Leo, the assistant of the Shosai workspace "{workspace_name}". A member wrote to you in the {messenger} chat "{chat_title}". Your reply is posted in that chat, where everyone in it can read it, including people who do not use Shosai.

Language: write the reply in the language of the message that addressed you. If that message is too short to tell, use the language of the chat's recent messages. Keep names, task titles and quoted words exactly as written.

Style: one or two short sentences of plain text. No headings, no emoji, no greeting and no sign-off. Use a list only to offer choices. Never reveal anything from Shosai that the people in this chat could not already see, beyond what the outcome below allows.
```

**Outcome: task created**

```text
Outcome: the task was created. Confirm it in one sentence: the task's title in quotation marks, who is responsible, and the due date if it has one. Then give the link on its own line.
Facts: title: {title}; responsible: {assignee_name, or "nobody yet"}; due: {due_date, or "no date"}; project: {project_name, or "none"}; link: {task_url}.
```

**Outcome: need clarification**

```text
Outcome: you need one answer before you can act. Ask {sender_name} exactly one short question about {missing}. When several members match a name, offer them by full name as choices, at most five. Say that they can answer by replying to this message. Do not create anything yet.
```

`{missing}` is one of the English phrases "who is responsible", "the due date", "which task you mean", "which project to put it in".

**Outcome: no rights**

```text
Outcome: the sender may not do this in the workspace: {reason}. Say in one sentence that you could not do it and why, in plain words. If it helps, say that a workspace admin can. Do not mention codes.
```

`{reason}` is one English phrase from the closed list the slice keeps with its refusal codes, for example "members may not create tasks in this project" or "the task belongs to a project the sender cannot see".

**English source of the fixed replies (CF-D6)** (user-facing text, worded in 16 languages through the backend's i18n catalog, not prompts):

- `chats.reply.not_linked`: "I can act only for people who linked their {messenger} account to Shosai. Link yours here: {link_url}"
- `chats.reply.confirm_slack` (a Slack member with a proposed link, CF-D4): "To act for you, I need you to confirm your Slack account in Shosai: {link_url}"
- `chats.reply.not_member`: "Your Shosai account isn’t a member of the workspace this chat is connected to, so I can’t act for you here. Ask a workspace admin to invite you."
- `chats.reply.not_connected` (the bot is in a group no workspace connected): "This chat isn’t connected to a Shosai workspace. A workspace admin can connect it in Shosai."

---

The sections that follow — facts, decisions of the backend, data, flows, the bot and webhooks, Leo's tools and the steps — are written by the `chats` slice's planning session.
