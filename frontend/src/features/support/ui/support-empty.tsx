"use client";

import { LifeBuoy, Plus, SearchX } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

/** No tickets yet: what support is for, and how to start. */
export function NoTickets({ onNew }: { onNew: () => void }) {
  const t = useTranslations("pagesSupport");
  return (
    <Empty className="rounded-xl border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <LifeBuoy />
        </EmptyMedia>
        <EmptyTitle>{t("list.emptyTitle")}</EmptyTitle>
        <EmptyDescription>{t("list.emptyDescription")}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button onClick={onNew}>
          <Plus data-icon="inline-start" />
          {t("newTicket")}
        </Button>
      </EmptyContent>
    </Empty>
  );
}

/** Tickets exist, but none match the search or filter. */
export function NoMatches() {
  const t = useTranslations("pagesSupport");
  return (
    <Empty className="rounded-xl border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <SearchX />
        </EmptyMedia>
        <EmptyTitle>{t("list.noMatchesTitle")}</EmptyTitle>
        <EmptyDescription>{t("list.noMatchesDescription")}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}
