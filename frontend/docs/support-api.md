# Support API

The contract between the Support page (tickets with a chat-style thread) and the FastAPI backend.
The TypeScript types in `src/features/support/domain/contract.ts` are the source of truth
(snake_case). The browser calls `/api/support/*`, which forwards to
`${BACKEND_API_URL}/v1/support/*` when set and otherwise answers from an in-memory demo
(`src/features/support/server/`, next to the route handlers). Errors: `{"detail": "message"}`, worded in the request's `Accept-Language`.

| Method  | Path                            | Body                                                  | Response         |
| ------- | ------------------------------- | ----------------------------------------------------- | ---------------- |
| `GET`   | `/support/tickets`              | —                                                     | `TicketsResponse` |
| `POST`  | `/support/tickets`              | multipart: `subject`, `category`, `body`, `files`     | `201 TicketDetail` |
| `GET`   | `/support/tickets/{id}`         | —                                                     | `TicketDetail` (marks read) |
| `POST`  | `/support/tickets/{id}/messages`| multipart: `body`, `files`                            | `TicketDetail`   |
| `PATCH` | `/support/tickets/{id}`         | `{"status": "open"\|"resolved"}`, `{"rating": "good"\|"bad"}` or `{"unread": bool}` | `TicketDetail` |

## Behaviour the UI relies on

- **Statuses:** `open` (waiting on support), `awaiting_you` (support replied), `resolved`. A reply
  to a resolved ticket reopens it; resolving or reopening adds a `system` message to the thread.
- **Messages** have `author: you | support | system`; support messages carry the teammate's
  `author_name`. System messages are events (opened, resolved, auto-acknowledgement), shown as
  separators; they carry an `event` code (`acknowledged`, `resolved`, `reopened`) that the UI words in
  the interface language, and `body` is shown as written only when the code is missing. `unread` is true when support replied after the user last opened the ticket.
- **Files:** up to 5 per message, 10 MB each (`MAX_ATTACHMENTS`, `MAX_ATTACHMENT_BYTES`). Store
  them and return `url`; the demo keeps only names and sizes (`url: null`).
- **Rating** is asked for once a ticket is resolved (`good` / `bad`).
- **Live updates** aren't wired yet: the UI refetches a ticket when it is opened. The backend
  should push new support replies (SSE or WebSocket) so the thread and unread dots update live.
- The demo never invents a teammate's reply; new tickets get an automatic acknowledgement only.
