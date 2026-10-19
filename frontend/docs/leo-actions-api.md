# Leo actions and sources API

What Leo proposes to do and what its answers stand on. Leo writes nothing without the person's consent: an
action arrives as a card with a server-made preview, then the person approves or declines it (Action Gateway,
[ADR 0025](../../docs/adr/0025-leo-action-gateway.md); [Leo architecture](../../docs/design/leo/ARCHITECTURE.md)
§5.3, §8.4, §13.2–13.3). An answer names its sources and the space each comes from
([ADR 0039](../../docs/adr/0039-one-account-per-person-with-workspaces.md) §7). The TypeScript types in
`src/features/leo/domain/proposals.ts` and `src/features/leo/domain/sources.ts` are the source of truth
(snake_case). The backend's `agent` slice is not built yet: the development mocks in `src/features/leo/mocks/`
answer the `/v1` paths below and the chat stream, so the cabinet shows the cards on sample data.

| Method | Path                                   | Body                                 | Response        |
| ------ | -------------------------------------- | ------------------------------------ | --------------- |
| `GET`  | `/v1/agent/actions?status=proposed`    | —                                    | `ProposalsPage` |
| `POST` | `/v1/agent/actions/{id}/approve`       | `{"accepted_changes"?: number[]}`    | `LeoProposal`   |
| `POST` | `/v1/agent/actions/{id}/reject`        | —                                    | `LeoProposal`   |

A decision on an action that no longer waits answers `409` with `action_not_pending`; the card then shows
the action's final state. Errors use the backend's envelope (ADR 0008).

## Chat stream events

Two events join the Leo chat stream (`src/features/leo/domain/protocol.ts`):

- `{"type": "proposal", "proposal": LeoProposal}` — an action from this answer waits for the person; the
  card renders under the answer, and "Needs you" reloads.
- `{"type": "sources", "sources": LeoSource[]}` — the answer's sources; the text marks a sentence with
  `[n]`, the n-th source counting from one.

SSE v2 (ADR 0032) has no event for sources yet: these shapes are the cabinet's proposal for the owner's
decision on how sources travel in Leo's stream, and only the demo agent sends them today.

## Behaviour the UI relies on

- **An action** has a `tool` (`mail.send`, `notes.update`, …; its family picks the icon), a `title`, the
  `space` it writes into, an `origin` (`thread`, `errand`, or `mcp` with the client's `app`), its
  `reversibility` (`irreversible` shows "Can't be undone"), `warning`, `taint` (the external text the action
  was prepared from, shown as is), a `preview`, `status`, `outcome`, `expires_at` and `resolved_at`.
- **The preview is the server's**, never the model's: `fields` (label and value pairs, an optional body) or
  `diff` (a text edit as `equal` and `change` segments). The labels arrive in the person's language.
- **A text edit** is shown inline: removed words struck through, new words marked. Each change can be taken
  or left, all or none; `approve` sends the indexes of the taken changes as `accepted_changes`, and "Apply"
  is disabled while none is taken.
- **Deciding.** ⌘/Ctrl+Enter approves and Esc declines while the card has focus. A decided action collapses
  into one line with its outcome; `outcome_unknown` asks the person to check.
- **"Needs you"** on the home screen lists every action with `status: proposed`, newest first, as collapsed
  rows ("Review" opens the card); it disappears when nothing waits.
- **Sources.** A marker for a source the answer did not send is not drawn. Pointing at a marker or a source
  lights the sentences that rest on it; pressing one opens the quote with its words highlighted, the space and
  the place inside (`locator`, such as a time in a recording).
