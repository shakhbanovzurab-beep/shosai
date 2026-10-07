import { MAX_ATTACHMENT_BYTES, MAX_ATTACHMENTS, TICKET_CATEGORIES, type Ticket, type TicketCategory } from "./contract";

export const isTicketCategory = (value: unknown): value is TicketCategory =>
  TICKET_CATEGORIES.some((category) => category === value);

export type TicketFilter = "open" | "resolved" | "all";

export const matchesFilter = (t: Ticket, filter: TicketFilter) =>
  filter === "all" || (filter === "resolved") === (t.status === "resolved");

/** Adds files within the limits: drops those over 10 MB and keeps at most MAX_ATTACHMENTS, saying what was dropped. */
export function limitAttachments<T extends { name: string; size: number }>(current: T[], incoming: T[]) {
  const tooBig = incoming.filter((f) => f.size > MAX_ATTACHMENT_BYTES);
  const next = [...current, ...incoming.filter((f) => f.size <= MAX_ATTACHMENT_BYTES)];
  return { files: next.slice(0, MAX_ATTACHMENTS), tooBig, overLimit: next.length > MAX_ATTACHMENTS };
}
