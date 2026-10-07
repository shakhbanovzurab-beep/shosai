# Mail insights API

The contract between the inbox (`/app/inbox`) and the FastAPI backend for Leo's reading of the user's
email. The TypeScript types in `src/features/mail/domain/leo-insights.ts` are the source of truth
(snake_case). The browser calls `/api/mail/insights`, which forwards to
`${BACKEND_API_URL}/v1/mail/insights` when set and otherwise answers from an in-memory demo
(`src/features/mail/server/`, fixtures in `src/features/mail/data/leo-insights*.ts`).
Errors: `{"detail": "message"}`.

| Method | Path              | Body | Response               |
| ------ | ----------------- | ---- | ---------------------- |
| `GET`  | `/mail/insights`  | —    | `MailInsightsResponse` |

## Behaviour the UI relies on

- **One insight per inbox email**, keyed by `mail_id`. An email without an insight gets no Leo card.
- **Status:** `analyzing` while Leo reads a new email (every reading field `null`, `key_points: []`),
  then `ready`, or `failed`. While any insight is `analyzing` the UI polls every 1.5 s.
- **Triage:** `needs_you` (waiting on the user's reply or decision), `fyi` (worth knowing, nothing to
  do) or `low` (can wait, stale, or noise). The "Needs you" view lists `needs_you` emails that are in
  the inbox and not yet replied to, earliest `reply_by` first, then newest.
- **`next_step`** is a short task ("Confirm a time for tomorrow's meeting"), shown in place of the
  preview in the "Needs you" view and above the summary in the email's Leo card. Only needed for
  `needs_you`.
- **`summary`**: one or two sentences. **`key_points`**: up to three short facts (asks, dates,
  attachments).
- **`reply_by`**: ISO timestamp when the sender needs an answer, if stated or implied; the UI shows
  "Overdue", "Reply today", "Reply tomorrow" or "Reply by Fri".
- **Language:** `next_step`, `summary`, `key_points` and `draft` are written by the model in the
  user's language, never translated by the frontend. The proxy sends the interface language as
  `Accept-Language`; the UI refetches when the user switches languages. `reply_by` stays an ISO
  timestamp: the UI words and formats it.
- **`draft`**: a reply in the user's voice, or `null` when Leo leaves the reply to the user (e.g.
  feedback that needs their own review). The user reviews and edits it; nothing is sent without
  their click on Send.

## Not wired to the backend yet

These stay in the browser session until the mail backend exists:

- **Sending** a reply (Leo's draft or the quick reply) marks the email replied locally, with Undo.
- **Draft edits and discards.** The backend should store the edited text as a real draft.
- **Re-sorting** an email ("Sorted as" menu). The backend should accept this as feedback, e.g.
  `PATCH /mail/insights/{mail_id}` with `{"triage": "fyi"}`, and return the updated insight.
- **Archiving**, including "Archive low priority" for all `low` emails at once.
- **Live updates:** the UI refetches on load and on the inbox's refresh button. The backend should
  push new insights (SSE or WebSocket) as mail arrives.
