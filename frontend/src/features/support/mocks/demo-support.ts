import type {
  Ticket,
  TicketAttachment,
  TicketCategory,
  TicketDetail,
  TicketEvent,
  TicketMessage,
  UpdateTicketRequest,
} from "../domain/contract";

/*
 * In-memory stand-in for the support desk, used when BACKEND_API_URL is unset; resets on restart.
 * There is no real teammate here: new messages get an automatic acknowledgement, never a fake reply.
 * Messages are what people wrote, so they stay as written; system events carry a code the UI words in the
 * interface language, with an English body for clients that don't know the code.
 */

const hoursAgo = (h: number) => new Date(Date.now() - h * 3600000).toISOString();
const now = () => new Date().toISOString();
const EVENT_BODIES: Record<TicketEvent, string> = {
  acknowledged: "We’ve got your message. A specialist usually replies within a few hours — we’ll notify you here.",
  resolved: "Marked as resolved",
  reopened: "Reopened",
};

type Draft = Omit<TicketMessage, "id" | "attachments"> & { attachments?: TicketAttachment[] };
const msg = (m: Draft): TicketMessage => ({ id: crypto.randomUUID(), attachments: [], ...m });
const system = (event: TicketEvent, created_at = now()) =>
  msg({ author: "system", author_name: null, event, body: EVENT_BODIES[event], created_at });

const seed = (): TicketDetail[] => [
  {
    id: "t-1042",
    number: 1042,
    subject: "Google Drive won’t connect to Knowledge base",
    category: "bug",
    status: "awaiting_you",
    unread: true,
    rating: null,
    last_message: "",
    created_at: hoursAgo(30),
    updated_at: hoursAgo(5),
    messages: [
      msg({
        author: "you",
        author_name: null,
        created_at: hoursAgo(30),
        body: "When I click “Continue with Google” in Knowledge base › Sources, the page reloads and nothing is connected.",
      }),
      system("acknowledged", hoursAgo(30)),
      msg({
        author: "support",
        author_name: "Maya",
        created_at: hoursAgo(5),
        body: "Thanks for the details! We fixed a redirect issue with Google sign-in this morning. Could you try once more and let me know if it still happens?",
      }),
    ],
  },
  {
    id: "t-1039",
    number: 1039,
    subject: "Company VAT number on invoices",
    category: "billing",
    status: "resolved",
    unread: false,
    rating: null,
    last_message: "",
    created_at: hoursAgo(80),
    updated_at: hoursAgo(60),
    messages: [
      msg({
        author: "you",
        author_name: null,
        created_at: hoursAgo(80),
        body: "Can you add our VAT number DE123456789 to future invoices?",
      }),
      system("acknowledged", hoursAgo(80)),
      msg({
        author: "support",
        author_name: "Daniel",
        created_at: hoursAgo(62),
        body: "Done — it’ll appear on every invoice from now on, starting with this month’s.",
      }),
      system("resolved", hoursAgo(60)),
    ],
  },
  {
    id: "t-1046",
    number: 1046,
    subject: "Export Kanban board to CSV",
    category: "feature",
    status: "open",
    unread: false,
    rating: null,
    last_message: "",
    created_at: hoursAgo(2),
    updated_at: hoursAgo(2),
    messages: [
      msg({
        author: "you",
        author_name: null,
        created_at: hoursAgo(2),
        body: "It would help a lot to export a board with all columns and due dates to CSV.",
      }),
      system("acknowledged", hoursAgo(2)),
    ],
  },
];

const shared = globalThis as typeof globalThis & { supportDemo?: Map<string, TicketDetail> };
shared.supportDemo ??= new Map(seed().map((t) => [t.id, t]));
const store = shared.supportDemo;

/** The latest message from a person, for the list preview. */
const preview = (t: TicketDetail) => t.messages.findLast((m) => m.author !== "system")?.body ?? "";
function summary(ticket: TicketDetail): Ticket {
  const { messages: _thread, ...rest } = ticket;
  return { ...rest, last_message: preview(ticket) };
}
const detail = (t: TicketDetail): TicketDetail => ({ ...t, last_message: preview(t) });

export const listTickets = (): Ticket[] =>
  [...store.values()].map(summary).toSorted((a, b) => b.updated_at.localeCompare(a.updated_at));

export function getTicket(id: string): TicketDetail | null {
  const t = store.get(id);
  if (!t) return null;
  t.unread = false;
  return detail(t);
}

export function createTicket(subject: string, category: TicketCategory, body: string, attachments: TicketAttachment[]) {
  const number = Math.max(1000, ...[...store.values()].map((t) => t.number)) + 1;
  const t: TicketDetail = {
    id: `t-${number}`,
    number,
    subject,
    category,
    status: "open",
    unread: false,
    rating: null,
    last_message: "",
    created_at: now(),
    updated_at: now(),
    messages: [msg({ author: "you", author_name: null, body, attachments, created_at: now() }), system("acknowledged")],
  };
  store.set(t.id, t);
  return detail(t);
}

/** Your reply; replying to a resolved ticket reopens it. */
export function addMessage(id: string, body: string, attachments: TicketAttachment[]): TicketDetail | null {
  const t = store.get(id);
  if (!t) return null;
  if (t.status === "resolved") t.messages.push(system("reopened"));
  t.messages.push(msg({ author: "you", author_name: null, body, attachments, created_at: now() }));
  t.status = "open";
  t.updated_at = now();
  return detail(t);
}

export function updateTicket(id: string, { status, rating, unread }: UpdateTicketRequest): TicketDetail | null {
  const t = store.get(id);
  if (!t) return null;
  if (status && status !== (t.status === "resolved" ? "resolved" : "open")) {
    t.messages.push(system(status === "resolved" ? "resolved" : "reopened"));
    t.status = status;
    t.updated_at = now();
  }
  if (rating) t.rating = rating;
  if (unread !== undefined) t.unread = unread;
  return detail(t);
}
