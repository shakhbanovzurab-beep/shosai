# ADR 0025 — One Action Gateway for every write, with durable proposals and single execution

- **Status:** accepted by the owner on 2026-10-08. **Amended** the "writing action guarded by a one-time key" clause of [ARCHITECTURE.md](../design/ARCHITECTURE.md) §8.1; implements inv-12.
- **Packages:** S09 (`agent`), S11, S10, S05, and every slice that ships write tools.
- **Context documents:** [Leo architecture](../design/leo/ARCHITECTURE.md) §8.1, §8.4; [Leo audit](../design/leo/AUDIT.md) A1–A3, A8, A9, P4; ARCHITECTURE.md inv-12, §14 rule 1.

## Context

The draft's confirmation protocol is well designed at the surface:

- the action is held on the server;
- the client sends only `interrupt_id` and yes/no;
- `confirm` has no side effects;
- the preview is computed by the server.

Underneath, the guarantee does not hold:

- **A1.** The one-time claim is a Redis key that lives 60 s, while the card lives 1 h. Batch items commit one by one and the checkpoint is written asynchronously. A crash or deadline after some commits leaves the interrupt pending, and a second approval re-executes it. No idempotency key reaches the domain or the external provider.
- **A2.** In voice, the voice model's own tool call approves.
- **A3.** MCP writes run without any confirmation.
- **A8.** Execution re-queries targets up to an hour after the preview, so it can delete more than was shown.
- **A9.** Some tools commit inside the handler, outside the audited transaction.
- **P4.** Errands send email without a lock or a key, retry without a lateness bound, and run duplicate workflows.

## Decision

1. **The only write path** is the Action Gateway. A tool whose `effect` is `write` (ADR 0029) is never executed by the run graph directly. This holds on every channel: turn, proactive, errand, MCP and voice.
2. **Durable proposals** live in `agent_actions` in the home DB. The row holds origin, the items (tool, **planned effect**, redacted arguments, the preview shown), friction and taint, `nonce`, `not_before`, `expires_at`, the approval channel and time, and per-item outcomes.
3. **Plan, then execute the plan.**
   - At proposal time, `plan()` freezes the exact targets (ids, counts, recipients).
   - `preview()` renders them.
   - `execute()` applies the effect only to those targets, after the owner slice re-checks access and entitlement.
4. **Single winner.** Each transition (`proposed → approved → executing → terminal`) is one conditional `UPDATE … RETURNING`. Concurrent approvals from tabs, voice, MCP or a double click yield one executor.
5. **Idempotent effects.** Item key = `action_id:index`, passed to `execute`. The slice records processed keys in the effect's own transaction, together with an outbox audit event.
6. **External effects use a write-ahead discipline:**
   1. commit `executing(item)`;
   2. call the provider, with its idempotency key where it supports one;
   3. commit the outcome.

   A crash in between yields `outcome_unknown`: never retried automatically, and reported to the user. At most once wins over at least once.
7. **Expiry.** Interactive proposals expire after 1 h. Proposals from initiative expire with their suggestion (≤ 24 h). Errand approvals are valid until `not_before` + the tolerance the user saw. A proposal without an expiry is impossible by constraint.
8. **Secrets** go through a one-time Valkey vault (`GETDEL`, 5 min) submitted with the approval request. They are never accepted by voice and never stored in rows, messages or checkpoints.
9. **Confirmation channels:**
   - web card and approvals inbox;
   - native, later;
   - voice, only for reversible or compensable actions, and only when **both** the server-side transcript is judged an approval and the voice model confirms the same action id;
   - MCP: a write returns `pending_approval`, and the human approves in the cabinet.

   Persistent-injection sinks (personalization, prompts, user context) are not writable over MCP.
10. **Audit:**
    - item effects through the outbox, `agent.action_item.executed` with ids and codes and no content (the event type follows `slice.object.happened`);
    - rejections and expiries recorded by the gateway;
    - `agent_audit` is partitioned monthly, kept 12 months, and append-only by role.

## Alternatives considered

| Option | Why not |
|---|---|
| Keep the interrupt in the checkpoint plus a Redis claim with a longer TTL | the claim and the effect are still not in one store; any TTL leaves a window; Valkey loss loses the pending action |
| Exactly-once by retries plus idempotency everywhere | external providers (mail, CRM, chat) do not all accept idempotency keys; retrying a send can duplicate it; inv-12 asks for at most once |
| Execute the action inside the graph's `act` node (draft) | ties a durable promise to a 24-h framework snapshot; a lost checkpoint loses the outcome |
| One transaction spanning the gateway and the slice | the slice owns its tables and its access policy; cross-slice transactions break §5 boundaries; the outbox gives the same durability |
| Voice approval by the voice model alone (draft) | A2: a model approving on the user's behalf |

## Consequences

- inv-12 becomes testable. Property tests drive concurrent approvals and crashes at every step, and invariant monitors count double execution and execution without approval.
- Every write tool must implement `plan`, `preview` and an idempotent `execute`. That is more work per tool, but it is the price of the invariant.
- **The approvals inbox** becomes possible. Pending actions survive any Valkey loss.
- `outcome_unknown` is a visible product state, with copy for "may have been sent".

## Revisit when

- The owner decides on standing approvals (architecture §17 Q-4), which would amend inv-12.
- A provider used by a write tool offers transactional idempotency, which would let that tool's `outcome_unknown` be retried safely.
