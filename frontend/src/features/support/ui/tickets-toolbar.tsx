"use client";

import { Plus, Search } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import type { TicketFilter } from "../domain/tickets";

type TicketsToolbarProps = {
  query: string;
  onQuery: (query: string) => void;
  filter: TicketFilter;
  onFilter: (filter: TicketFilter) => void;
  counts: Record<TicketFilter, number>;
  onNew: () => void;
};

/** Search, All / Open / Resolved with counts, and New ticket. */
export function TicketsToolbar({ query, onQuery, filter, onFilter, counts, onNew }: TicketsToolbarProps) {
  const t = useTranslations("pagesSupport");
  const format = useFormatter();
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <InputGroup className="h-9 sm:max-w-72">
        <InputGroupAddon>
          <Search />
        </InputGroupAddon>
        <InputGroupInput
          type="search"
          value={query}
          onChange={(e) => onQuery(e.currentTarget.value)}
          placeholder={t("toolbar.search")}
          aria-label={t("toolbar.search")}
        />
      </InputGroup>
      <ToggleGroup
        type="single"
        variant="outline"
        spacing={0}
        value={filter}
        onValueChange={(v) => (v === "open" || v === "resolved" || v === "all" ? onFilter(v) : undefined)}
        aria-label={t("toolbar.filter")}
      >
        <ToggleGroupItem value="all" className="px-3">
          {t("toolbar.all")} <span className="text-muted-foreground tabular-nums">{format.number(counts.all)}</span>
        </ToggleGroupItem>
        <ToggleGroupItem value="open" className="px-3">
          {t("toolbar.open")} <span className="text-muted-foreground tabular-nums">{format.number(counts.open)}</span>
        </ToggleGroupItem>
        <ToggleGroupItem value="resolved" className="px-3">
          {t("toolbar.resolved")}{" "}
          <span className="text-muted-foreground tabular-nums">{format.number(counts.resolved)}</span>
        </ToggleGroupItem>
      </ToggleGroup>
      <Button className="w-fit sm:ms-auto" onClick={onNew}>
        <Plus data-icon="inline-start" />
        {t("newTicket")}
      </Button>
    </div>
  );
}
