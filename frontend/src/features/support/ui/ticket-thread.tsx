"use client";

import { useTransition } from "react";

import { CircleCheck, RotateCcw, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import type { TicketDetail, UpdateTicketRequest } from "../domain/contract";
import { useSupport } from "../model/support-store";
import { replyToTicket, updateTicket } from "../model/ticket-actions";
import { TicketComposer } from "./ticket-composer";
import { TicketMessages } from "./ticket-messages";

/** Once resolved: a note that replying reopens the ticket, and a one-tap rating. */
function ResolvedFooter({ ticket, onUpdate }: { ticket: TicketDetail; onUpdate: (p: UpdateTicketRequest) => void }) {
  const t = useTranslations("pagesSupport");
  return (
    <div className="mx-3 mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-muted/40 px-4 py-3 text-sm">
      <span className="flex items-center gap-2">
        <CircleCheck className="size-4 text-muted-foreground" aria-hidden="true" />
        {t("thread.resolvedNote")}
      </span>
      {ticket.rating ? (
        <span className="text-muted-foreground">{t("thread.thanks")}</span>
      ) : (
        <span className="flex items-center gap-1">
          <span className="me-1 text-muted-foreground">{t("thread.rate")}</span>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={t("thread.good")}
            onClick={() => onUpdate({ rating: "good" })}
          >
            <ThumbsUp />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={t("thread.bad")}
            onClick={() => onUpdate({ rating: "bad" })}
          >
            <ThumbsDown />
          </Button>
        </span>
      )}
    </div>
  );
}

/** One ticket: header with status and resolve/reopen, the thread, and the reply box. */
export function TicketThread({ ticketId, onClose }: { ticketId: string; onClose: () => void }) {
  const t = useTranslations("pagesSupport");
  const { details, loadingId } = useSupport();
  const [pending, startTransition] = useTransition();
  const ticket = details[ticketId];

  if (!ticket || loadingId === ticketId) {
    return <Skeleton className="m-4 h-64 rounded-xl" aria-label={t("thread.loading")} />;
  }

  const update = (patch: UpdateTicketRequest) =>
    startTransition(async () => {
      await updateTicket(t, ticket.id, patch);
    });

  const reply = (body: string, files: File[]) => replyToTicket(t, ticket.id, body, files);

  const resolved = ticket.status === "resolved";
  return (
    <section aria-labelledby="ticket-subject-heading" className="flex h-full min-h-0 flex-col">
      <header className="flex items-center gap-2 border-b py-3 ps-4 pe-2">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <h2 id="ticket-subject-heading" dir="auto" className="truncate font-medium">
            {ticket.subject}
          </h2>
          <span className="text-muted-foreground text-xs">
            #{ticket.number} · {t(`categories.${ticket.category}`)}
          </span>
        </div>
        <Badge variant={resolved ? "secondary" : "outline"} className="hidden rounded-md 2xl:inline-flex">
          {t(`statuses.${ticket.status}`)}
        </Badge>
        <Button
          variant="outline"
          size="sm"
          disabled={pending}
          onClick={() => update({ status: resolved ? "open" : "resolved" })}
        >
          {resolved ? <RotateCcw data-icon="inline-start" /> : <CircleCheck data-icon="inline-start" />}
          {resolved ? t("thread.reopen") : t("thread.resolve")}
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label={t("thread.close")} onClick={onClose}>
          <X />
        </Button>
      </header>
      <TicketMessages messages={ticket.messages} />
      {resolved ? <ResolvedFooter ticket={ticket} onUpdate={update} /> : null}
      <TicketComposer
        key={ticket.id}
        placeholder={resolved ? t("composer.replyToReopen") : t("composer.reply")}
        onSend={reply}
      />
    </section>
  );
}
