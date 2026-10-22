# ADR 0063 — Team chats: the contract and the cabinet's screens

- **Status:** accepted by the owner on 2026-10-22, with the plan of the CHATS-frontend package: CF-D1…CF-D8, CF-D10 and CF-D11 as proposed, CF-D9 changed by the owner.
- **Packages:** `chats-frontend` (the cabinet on mocks), `chats` (the backend slice, which implements the contract as written), `identity` (step 18, the messenger link), `tasks` (TK-D13), `agent` (requirements AG-R1 and AG-R2).
- **Context documents:** [ADR 0062](0062-team-chats-through-leo-on-demand.md); [CHATS-frontend plan](../plan/packages/CHATS-frontend.md) §1–§2; [chats plan](../plan/slices/chats.md) §1; [tasks plan](../plan/slices/tasks.md) TK-D13 and §3.10; [identity plan](../plan/slices/identity.md) step 18; [agent plan](../plan/slices/agent.md); [Leo architecture](../design/leo/ARCHITECTURE.md) §8.4, §13.2.

## Context

ADR 0062 decided that a team's Telegram and Slack chats connect to a workspace and that Leo acts in them only on request, with the cabinet's screens built first on mocks of the slice's contract. Writing that contract against the messengers' own documentation showed points the ADR had not settled or had stated wrongly:

- Telegram's privacy mode is a setting of the bot, changed by its owner for every group at once; a group's admin cannot turn it off. Telegram delivers every message to bots that are a group's administrators.
- Telegram documents commands to a bot and replies to its messages as what a bot in privacy mode receives; plain mentions are not in that list.
- Slack can read a channel's past, but new installs of apps outside the Slack Marketplace get one `conversations.history` request a minute with 15 messages.
- Slack's API does not say a member's email is verified, and the address is managed inside the Slack workspace.

## Decision

1. **CF-D1 — "Every message" through the bot as an administrator.** Shosai's bot keeps privacy mode on. "Only messages to Leo" is the bot as an ordinary member; "Every message, for digests" is the group making the bot an administrator. The connect screen explains this and that every administrator right of the bot can be switched off, since it still receives the messages. Until Telegram reports the promotion the chat shows "rights missing" with "Make Leo an admin". ADR 0062 point 5 is amended.
2. **CF-D2 — Addressing Leo in Telegram.** The screens say "Mention @<bot> or reply to Leo's message"; the `chats` slice confirms on a live bot that a mention arrives in privacy mode, and otherwise the wording becomes "Start with /leo@<bot> or reply to Leo's message".
3. **CF-D3 — History.** Shosai keeps a chat's messages from its connection on, in Slack as in Telegram; reading a Slack channel's past is a later decision once Shosai is in the Slack Marketplace.
4. **CF-D4 — Slack matches are confirmed.** A Slack member whose Slack email equals their Shosai account's gets a proposed link that the person confirms once in Settings › Account ("Is this you?"); until then Leo answers them as not linked.
5. **CF-D5 — "Make a task" without a model round.** A digest item becomes an approval card directly: chats plans one `tasks.create` through the Action Gateway in the digest's thread; several items make one card.
6. **CF-D6 — Fixed replies for strangers.** Leo's replies to a sender who is not linked or not a member, and in a chat no workspace connected, are fixed messages the server sends without a model, worded by i18n in the sender's messenger language; the replies inside a run (task created, need clarification, no rights) are model-written under the English templates of chats §1.5.
7. **CF-D7 — The chat source on the card face is text.** The face shows the messenger's mark and the chat's name; the link to the message is in the card panel.
8. **CF-D8 — Retention.** A workspace setting of 30, 90 or 365 days, 90 by default, changed by admins; a shorter period erases older messages after a confirmation.
9. **CF-D9 — The hint for an unlinked member is the person's, for good** (changed by the owner from "per browser"). Once the person closes it, it does not come back in any workspace or on any device: the dismissal is a setting of the account, kept by `identity` with the messenger links.
10. **CF-D10 — Links per messenger account space.** One Telegram account per Shosai account and one Shosai account per Telegram account; Slack accounts one per Slack workspace.
11. **CF-D11 — The digest as Leo's artifact.** A new artifact kind `chat_digest` in Leo's stream, `{kind, ref: digest_id, alt, workspace_id, chat_id}`; the digest is kept by `chats` for 30 days and erased with the chat; the cabinet reads it by the chats route. Recorded as a requirement of the agent plan (AG-R1).
12. **The contract** of [chats §1](../plan/slices/chats.md), tasks TK-D13 and identity step 18 is approved as written with these decisions; a change needs the owner.

## Consequences

- The `chats` slice's planning session keeps the contract fixed and adds data, flows, the bot and webhooks, Leo's tools and steps; it confirms CF-D2 and the `admin=` value of CF-D1 on a live bot.
- `identity` gains step 18 (messenger links and the hint's dismissal); `tasks` gains the `chat` source (§3.10); `agent` gains AG-R1 (the artifact kind, amending Leo §13.2 when its plan is written) and AG-R2 (a port to create an approval card from a slice's planned call).
- SLICE_MAP §8.1's note on the messenger link follows CF-D10.
- A team that connects a chat gets digests only of what was written after the connection.

## Revisit when

- Shosai is approved for the Slack Marketplace → reading a channel's past at connection (CF-D3).
- The live check shows mentions do not reach a bot in privacy mode → the wording of CF-D2 changes, nothing else.
- People whose Slack email differs from their Shosai one ask to use Leo from Slack → a "Sign in with Slack" link.
