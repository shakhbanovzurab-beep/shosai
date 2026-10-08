import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import { SUBJECT_MAX, type TicketDetail, type TicketsResponse } from "../domain/contract";
import { isTicketCategory } from "../domain/tickets";
import { addMessage, createTicket, getTicket, listTickets, updateTicket } from "./demo-support";
import { parseMessage } from "./parse-message";
import { refuse } from "./problems";

type Context = { params: Promise<{ id: string }> };

const updateSchema = z
  .object({ status: z.enum(["open", "resolved"]), rating: z.enum(["good", "bad"]), unread: z.boolean() })
  .partial()
  .strict();

/** /api/support/tickets */
export const ticketsRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<TicketsResponse>({ tickets: listTickets() });
  },

  /** Opens a ticket: multipart with subject, category, body and optional files. */
  async POST(request: Request) {
    const parsed = await parseMessage(request);
    if ("problem" in parsed) return refuse(parsed.problem, 422);
    const { form, body, attachments } = parsed.message;
    const subject = String(form.get("subject") ?? "").trim();
    const category = form.get("category");
    if (!subject || subject.length > SUBJECT_MAX) return refuse({ code: "subjectRequired" }, 422);
    if (!isTicketCategory(category)) return refuse({ code: "topicRequired" }, 422);
    if (!body) return refuse({ code: "detailsRequired" }, 422);
    return JsonResponse.json<TicketDetail>(createTicket(subject, category, body, attachments), { status: 201 });
  },
};

/** /api/support/tickets/[id] */
export const ticketRoute = {
  /** The ticket with its whole thread; opening it marks support's replies as read. */
  async GET(_request: Request, { params }: Context) {
    const { id } = await params;
    const ticket = getTicket(id);
    return ticket ? JsonResponse.json(ticket) : refuse({ code: "ticketNotFound" }, 404);
  },

  /** Resolve or reopen, rate a resolved ticket, or mark it read/unread. */
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const body = updateSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return refuse({ code: "invalidUpdate" }, 422);
    const ticket = updateTicket(id, body.data);
    return ticket ? JsonResponse.json(ticket) : refuse({ code: "ticketNotFound" }, 404);
  },
};

/** /api/support/tickets/[id]/messages */
export const ticketMessagesRoute = {
  /** Your reply (multipart: body, files). Replying to a resolved ticket reopens it. */
  async POST(request: Request, { params }: Context) {
    const { id } = await params;
    const parsed = await parseMessage(request);
    if ("problem" in parsed) return refuse(parsed.problem, 422);
    const ticket = addMessage(id, parsed.message.body, parsed.message.attachments);
    return ticket ? JsonResponse.json(ticket) : refuse({ code: "ticketNotFound" }, 404);
  },
};
