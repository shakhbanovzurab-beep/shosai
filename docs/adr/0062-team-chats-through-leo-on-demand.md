# ADR 0062 — Team chats reach Shosai through connectors and Leo on demand

- **Status:** accepted by the owner on 2026-10-22.
- **Packages:** a new slice `chats`; `identity` (linking a messenger account); `agent` (Leo's chat tools run through its Action Gateway); `tasks` (tasks created from a chat carry their source); `connectors` (OAuth of the messengers that need it).
- **Context documents:** [CLAUDE.md](../../.claude/CLAUDE.md) "Philosophy"; [SLICE_MAP.md](../plan/SLICE_MAP.md) §4; [ADR 0029](0029-leo-tools-owned-by-domain-slices.md); [ADR 0039](0039-one-account-per-person-with-workspaces.md); [ARCHITECTURE.md](../design/ARCHITECTURE.md) §6.

## Context

- Teams already talk in Telegram, Slack and similar messengers. The owner asked whether workspaces should get Slack-like channels with Telegram-like messages (voice and video notes, media, polls, location).
- A messenger inside Shosai contradicts the philosophy (it takes attention instead of giving it back), cannot win the network effect of the messengers teams already use, and in Russia a service for exchanging messages may fall under the obligations of an "organiser of information dissemination" (registry, message retention, disclosure).
- What teams lack is not one more chat but memory of what was agreed in the chats they have.

## Decision

1. **No messenger in Shosai.** No channels, message feed, voice or video notes, polls, location or reactions.
2. **A slice `chats`** connects a team's existing chats to a workspace (or one of its projects): a Telegram group through Shosai's bot, a Slack channel through the Slack app; further messengers by the priority list of the slice plan. Only chats connected explicitly by a workspace admin are read; the bot is visible to every member of the chat.
3. **Leo works on demand, in two places:**
   - **in the chat:** "@Leo make this decision a task, Zurab is responsible" creates the task in the connected workspace and Leo answers in the chat with a short confirmation and a link; when something is ambiguous (two Zurabs, no clear deadline) Leo asks in the chat;
   - **in Shosai:** "go through the #release chat for the week — what matters?" gives a digest (decisions, open questions, who promised what) and offers to turn items into tasks.
   Leo never posts or creates anything in a chat or in Shosai on its own; proactive chat signals, if ever, are a separate decision in `proactive`.
4. **Who may command Leo.** A chat message is executed only for a sender whose messenger account is linked to a Shosai account (`identity`) and who is a member of the connected workspace; it runs with that member's rights through the Action Gateway. A person named as responsible is matched among the workspace's members; an unlinked or ambiguous name makes Leo ask.
5. **What is read and kept.** The bot reads only connected chats. Telegram delivers messages only from the moment the bot joins. *Amended by the owner on 2026-10-22 ([ADR 0063](0063-team-chats-contract-and-screens.md), CF-D1):* Telegram's privacy mode is a setting of the bot itself, not of a group, so Shosai's bot keeps it on everywhere. Where the bot is an ordinary member, only messages addressed to it (a mention or a reply to Leo) reach Shosai — the mode "Only messages to Leo". Reading every message, for digests, needs the group to make the bot an administrator, because Telegram delivers every message to bot administrators — the mode "Every message, for digests". The connect screen explains this to the admin, and also that every administrator right of the bot can be switched off: it still receives the messages. Messages are stored in the workspace's home, labelled foreign text for Leo (like `task:foreign`), kept for a retention set in settings, and erased with the chat's disconnection or the workspace.
6. **Frontend first.** The cabinet's screens are built first on mocks of the slice's `/v1` contract (package `CHATS-frontend`), then the backend slice implements that contract.

## Consequences

- One new slice and two small additions (`identity`: messenger account link; `tasks`: a `chat` source on tasks).
- Shosai stores team chat messages of connected chats: personal data of chat members who are not Shosai users. The connect screen states this, the workspace admin accepts it, and the privacy policy names it; the legal review of §22 covers it before launch.
- Shosai is not a message service: it neither delivers messages between people nor hosts chats.

## Revisit when

- Users ask for Leo to notice important things in chats without being asked → a `proactive` source with its budgets and quiet hours.
- A messenger outside the priority list is requested by paying teams → it joins the list.
