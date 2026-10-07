"use client";

import { create } from "zustand";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource } from "@/lib/polling-resource";

import { supportApi } from "../api/support-api";
import type { Ticket, TicketDetail } from "../domain/contract";

export const ticketsResource = createPollingResource(supportApi.list);

export const useTickets = () => usePollingResource(ticketsResource);

/** The list row for a ticket, kept in step with the detail we just received. */
function syncListRow(ticket: TicketDetail) {
  const { messages: _thread, ...row } = ticket;
  ticketsResource.update((data) => ({
    tickets: [row as Ticket, ...data.tickets.filter((t) => t.id !== ticket.id)].toSorted((a, b) =>
      b.updated_at.localeCompare(a.updated_at),
    ),
  }));
}

type SupportState = {
  /** A ticket id, "new" for the new-ticket form, or null for the welcome panel. */
  selected: string | null;
  details: Record<string, TicketDetail>;
  loadingId: string | null;
  /** Shows a ticket, the new-ticket form or nothing; `showTicket` also fetches the ticket's thread. */
  select: (selection: string | null) => void;
  /** Stores a ticket returned by the API and refreshes its row in the list. */
  receive: (ticket: TicketDetail) => void;
};

export const useSupport = create<SupportState>((set) => ({
  selected: null,
  details: {},
  loadingId: null,
  receive: (ticket) => {
    set((s) => ({ details: { ...s.details, [ticket.id]: ticket } }));
    syncListRow(ticket);
  },
  select: (selection) => set({ selected: selection }),
}));
