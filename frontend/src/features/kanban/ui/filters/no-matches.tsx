"use client";

import { SearchX } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

import { clearFilter } from "./filter-address";

/** Под фильтром не нашлось ни одной задачи: сказать это и дать сбросить фильтры одним действием. */
export function NoMatches() {
  const t = useTranslations("kanbanFilters");
  return (
    <Empty className="flex-1">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <SearchX />
        </EmptyMedia>
        <EmptyTitle>{t("noMatches")}</EmptyTitle>
        <EmptyDescription>{t("noMatchesHint")}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button variant="outline" onClick={clearFilter}>
          {t("clear")}
        </Button>
      </EmptyContent>
    </Empty>
  );
}
