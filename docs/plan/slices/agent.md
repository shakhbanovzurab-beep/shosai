# agent — slice plan

Slice card: [SLICE_MAP.md §4.2.14–18](../SLICE_MAP.md#1418-leo-agent-decisions-memory-proactive-errands). Design: [Leo architecture](../../design/leo/ARCHITECTURE.md). Status: [STATUS.md](../STATUS.md), row `agent`.

The plan itself is written by the `agent` slice's planning session ([S-feature-slice.md](../prompts/S-feature-slice.md)). Until then this file holds the requirements other plans recorded for it. Each is decided by the owner; the planning session keeps it as written or brings a change to the owner.

## Requirements recorded before this plan

| ID | From | Requirement | Decided |
|---|---|---|---|
| **AG-R1** | [CHATS-frontend](../packages/CHATS-frontend.md) CF-D11, [ADR 0063](../../adr/0063-team-chats-contract-and-screens.md) | **The artifact kind `chat_digest`.** Leo's stream (§13.2, SSE v2) carries a chat's digest as `artifact {kind: "chat_digest", ref: <digest_id>, alt, workspace_id, chat_id}`, emitted when `chats.digest` returns; the thread's history (`GET /v1/agent/threads/{id}/messages`) returns it in the message's artifacts. The thread keeps only the reference: the digest is kept by `chats` for 30 days and erased with the chat's disconnection or its messages' retention, and the cabinet reads it by `GET /v1/workspaces/{id}/chats/{chat_id}/digests/{digest_id}` ([chats plan](chats.md) §1.3). Leo §13.2's list of artifact kinds is amended by this plan | The owner, 2026-10-22: "record CF-D11 as a requirement in the agent plan" |
| **AG-R2** | CHATS-frontend CF-D5, ADR 0063 | **An approval card from a slice's planned call, without a model round.** A port lets a slice put a proposal into a thread through the Action Gateway: chats' `POST /v1/workspaces/{id}/chats/{chat_id}/digests/{digest_id}/task-proposals {item_ids}` plans one `tasks.create` (a task per item) in the digest's thread with the person as principal and returns the stored action in the cabinet's `LeoProposal` shape; the card is approved, expires and is audited like any other (§8.4); the tasks carry the `chat` source (tasks TK-D13), set from the items, never from a model | CF-D5 by the owner, 2026-10-22; the port is its consequence, as the plan worded it |
