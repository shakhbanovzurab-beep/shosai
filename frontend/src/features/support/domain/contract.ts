/**
 * Support API contract, shared by the Support page and the route handlers in `server/` (mounted
 * under `src/app/api/support`). They forward to `${BACKEND_API_URL}/v1/support/*` when it is set
 * and otherwise answer from an in-memory demo. snake_case to match Pydantic; errors are
 * `{ "detail": string }`. See docs/support-api.md.
 *
 * GET  /support/tickets                → TicketsResponse
 * POST /support/tickets                → 201 TicketDetail   (multipart: subject, category, body, files)
 * GET  /support/tickets/{id}           → TicketDetail       (also marks it read)
 * POST /support/tickets/{id}/messages  → TicketDetail       (multipart: body, files; reopens a resolved ticket)
 * PATCH /support/tickets/{id}          → TicketDetail       (UpdateTicketRequest)
 */

/** "open": waiting on support; "awaiting_you": support replied; "resolved": closed, can be reopened by replying. */
export type TicketStatus = "open" | "awaiting_you" | "resolved";

/** Topic codes; the UI words each one in the interface language. */
export const TICKET_CATEGORIES = ["billing", "bug", "account", "feature", "other"] as const;

export type TicketCategory = (typeof TICKET_CATEGORIES)[number];

/** What a system message records; the UI words it in the interface language. */
export type TicketEvent = "acknowledged" | "resolved" | "reopened";

export type TicketAttachment = { name: string; size_bytes: number; url: string | null };

export type TicketMessage = {
  id: string;
  /** "system" is an event in the thread (opened, resolved, auto-acknowledgement), not a person. */
  author: "you" | "support" | "system";
  /** The support teammate's name; null for you and for system events. */
  author_name: string | null;
  /** A system message's event code, worded by the UI; without one, `body` is shown as written. */
  event?: TicketEvent | null;
  body: string;
  attachments: TicketAttachment[];
  created_at: string;
};

export type Ticket = {
  id: string;
  /** Human-facing number, shown as #1042. */
  number: number;
  subject: string;
  category: TicketCategory;
  status: TicketStatus;
  /** Support replied and you haven't opened the ticket since. */
  unread: boolean;
  /** Asked for once a ticket is resolved. */
  rating: "good" | "bad" | null;
  last_message: string;
  created_at: string;
  updated_at: string;
};

export type TicketDetail = Ticket & { messages: TicketMessage[] };
export type TicketsResponse = { tickets: Ticket[] };
export type UpdateTicketRequest = {
  status?: "open" | "resolved";
  rating?: "good" | "bad";
  /** Mark as unread to come back to it later; opening the ticket marks it read again. */
  unread?: boolean;
};

export const SUBJECT_MAX = 120;
export const BODY_MAX = 5000;
export const MAX_ATTACHMENTS = 5;
export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
