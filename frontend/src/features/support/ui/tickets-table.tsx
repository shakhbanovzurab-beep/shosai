"use client";

import { cn } from "cn";
import { useFormatter, useNow, useTranslations } from "next-intl";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { Ticket } from "../domain/contract";
import { TicketContextMenu } from "./ticket-context-menu";

type TicketsTableProps = { tickets: Ticket[]; selected: string | null; onOpen: (id: string) => void };

/** Every ticket as a row; click or press Enter to open it in the side panel, right-click for more actions. */
export function TicketsTable({ tickets, selected, onOpen }: TicketsTableProps) {
  const t = useTranslations("pagesSupport");
  const format = useFormatter();
  // "5 minutes ago" moves on by itself; the table renders in the browser only, after the tickets load.
  const now = useNow({ updateInterval: 60_000 });
  return (
    <div className="overflow-hidden rounded-xl border bg-card shadow-xs">
      <Table>
        <TableHeader className="bg-muted/50">
          <TableRow>
            <TableHead className="w-20 ps-4">{t("table.number")}</TableHead>
            <TableHead>{t("table.subject")}</TableHead>
            <TableHead className="hidden md:table-cell">{t("table.status")}</TableHead>
            <TableHead className="hidden xl:table-cell">{t("table.topic")}</TableHead>
            <TableHead className="hidden pe-4 text-end sm:table-cell">{t("table.updated")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tickets.map((ticket) => (
            <TicketContextMenu key={ticket.id} ticket={ticket} onOpen={onOpen}>
              <TableRow
                tabIndex={0}
                aria-selected={selected === ticket.id}
                onClick={() => onOpen(ticket.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onOpen(ticket.id);
                  }
                }}
                className={cn(
                  "cursor-pointer focus-visible:outline-2 focus-visible:outline-ring focus-visible:-outline-offset-2 data-[state=open]:bg-muted",
                  selected === ticket.id && "bg-muted",
                )}
              >
                <TableCell className="ps-4 font-mono text-muted-foreground tabular-nums">#{ticket.number}</TableCell>
                <TableCell className="w-full max-w-0">
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="flex min-w-0 items-center gap-2">
                      {ticket.unread ? (
                        <>
                          <span className="size-2 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                          <span className="sr-only">{t("table.unread")}</span>
                        </>
                      ) : null}
                      <span dir="auto" className={cn("truncate", ticket.unread && "font-semibold")}>
                        {ticket.subject}
                      </span>
                    </span>
                    <span dir="auto" className="truncate text-muted-foreground text-xs">
                      {ticket.last_message}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="hidden whitespace-nowrap md:table-cell">
                  {t(`statuses.${ticket.status}`)}
                </TableCell>
                <TableCell className="hidden whitespace-nowrap text-muted-foreground xl:table-cell">
                  {t(`categories.${ticket.category}`)}
                </TableCell>
                <TableCell className="hidden whitespace-nowrap pe-4 text-end text-muted-foreground sm:table-cell">
                  {format.relativeTime(new Date(ticket.updated_at), now)}
                </TableCell>
              </TableRow>
            </TicketContextMenu>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
