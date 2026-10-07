"use client";

import { type ReactNode, useDeferredValue, useState } from "react";

import { useTranslations } from "next-intl";

import { LoadError } from "@/components/feedback";
import { useDirection } from "@/components/ui/direction";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useIsLg } from "@/hooks/use-lg";

import { matchesFilter, type TicketFilter } from "../domain/tickets";
import { ticketsResource, useSupport, useTickets } from "../model/support-store";
import { showTicket } from "../model/ticket-actions";
import { NewTicketForm } from "./new-ticket-form";
import { NoMatches, NoTickets } from "./support-empty";
import { SupportSplit } from "./support-split";
import { TicketThread } from "./ticket-thread";
import { TicketsTable } from "./tickets-table";
import { TicketsToolbar } from "./tickets-toolbar";

/** The open ticket or the new-ticket form, shown in the side panel (lg+) or a sheet (smaller screens). */
function Panel({ selected, onClose }: { selected: string; onClose: () => void }) {
  return selected === "new" ? (
    <NewTicketForm onClose={onClose} />
  ) : (
    <TicketThread key={selected} ticketId={selected} onClose={onClose} />
  );
}

/** Tickets as a full-width table; the selected one opens in a panel beside it, so the table stays in view. */
export function SupportView() {
  const t = useTranslations("pagesSupport");
  const tickets = useTickets();
  const { selected, select } = useSupport();
  const isLg = useIsLg();
  // The sheet slides in from the end edge: the right in left-to-right languages, the left in Arabic.
  const sheetSide = useDirection() === "rtl" ? "left" : "right";
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<TicketFilter>("all");
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());
  const close = () => select(null);
  const openNew = () => select("new");
  const open = (id: string) => showTicket(t, id);

  const all = tickets.status === "ready" ? tickets.data.tickets : [];
  const resolved = all.filter((ticket) => ticket.status === "resolved").length;
  const counts = { open: all.length - resolved, resolved, all: all.length };
  const visible = all.filter(
    (ticket) =>
      matchesFilter(ticket, filter) &&
      (!deferredQuery ||
        `#${ticket.number} ${ticket.subject} ${ticket.last_message}`.toLowerCase().includes(deferredQuery)),
  );

  let body: ReactNode;
  if (tickets.status === "loading") body = <Skeleton className="h-64 rounded-xl" aria-label={t("list.loading")} />;
  else if (tickets.status === "error")
    body = (
      <LoadError title={t("list.loadError")} message={tickets.message} onRetry={() => void ticketsResource.refresh()} />
    );
  else if (all.length === 0) body = <NoTickets onNew={openNew} />;
  else if (visible.length === 0) body = <NoMatches />;
  else body = <TicketsTable tickets={visible} selected={selected} onOpen={open} />;

  const list = (
    <div className="flex h-full min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-4 md:p-6">
      <TicketsToolbar
        query={query}
        onQuery={setQuery}
        filter={filter}
        onFilter={setFilter}
        counts={counts}
        onNew={openNew}
      />
      {body}
    </div>
  );

  return (
    <div className="flex h-[calc(100dvh-var(--dashboard-header-height))] min-h-0 overflow-hidden">
      {isLg ? (
        <SupportSplit table={list} panel={selected === null ? null : <Panel selected={selected} onClose={close} />} />
      ) : (
        <>
          {list}
          <Sheet open={selected !== null} onOpenChange={(isOpen) => (isOpen ? undefined : close())}>
            <SheetContent side={sheetSide} showCloseButton={false} className="w-full gap-0 p-0 sm:max-w-lg">
              <SheetTitle className="sr-only">{selected === "new" ? t("newTicket") : t("panel.ticket")}</SheetTitle>
              <SheetDescription className="sr-only">{t("panel.description")}</SheetDescription>
              {selected === null ? null : <Panel selected={selected} onClose={close} />}
            </SheetContent>
          </Sheet>
        </>
      )}
    </div>
  );
}
