"use client";

import { useState } from "react";

import { Search } from "lucide-react";
import { useLocale } from "use-intl";

import { Button } from "@/components/ui/button";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { ItemGroup } from "@/components/ui/item";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { MEMORY_KINDS, type MemoryFact } from "../domain/contract";
import { countByKind, filterFacts, groupByKind, type KindFilter } from "../domain/facts";
import type { MemoryWords } from "../model/fact-actions";
import { FactItem } from "./fact-item";

const isKindFilter = (value: string): value is KindFilter =>
  value === "all" || MEMORY_KINDS.some((kind) => kind === value);

type FactListProps = {
  active: MemoryFact[];
  words: MemoryWords;
  /** «Показать ещё» — пока у сервера есть следующая страница. */
  onMore: (() => void) | null;
};

/** Принятые факты: фильтр по видам со счётчиками, поиск и группы по видам. */
export function FactList({ active, words, onMore }: FactListProps) {
  const { t } = words;
  const locale = useLocale();
  const [kind, setKind] = useState<KindFilter>("all");
  const [query, setQuery] = useState("");
  const counts = countByKind(active);
  const shown = filterFacts(active, kind, query, locale);
  const groups = groupByKind(shown);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={kind}
          aria-label={t("kinds.label")}
          className="flex-wrap"
          onValueChange={(value) => (isKindFilter(value) ? setKind(value) : undefined)}
        >
          <ToggleGroupItem value="all">
            {t("kinds.all")}
            <span className="text-muted-foreground tabular-nums">{active.length}</span>
          </ToggleGroupItem>
          {MEMORY_KINDS.filter((k) => counts[k] > 0).map((k) => (
            <ToggleGroupItem key={k} value={k}>
              {t(`kinds.${k}`)}
              <span className="text-muted-foreground tabular-nums">{counts[k]}</span>
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <InputGroup className="sm:ms-auto sm:w-56">
          <InputGroupAddon>
            <Search />
          </InputGroupAddon>
          <InputGroupInput
            type="search"
            value={query}
            placeholder={t("search")}
            aria-label={t("search")}
            onChange={(event) => setQuery(event.target.value)}
          />
        </InputGroup>
      </div>
      {shown.length === 0 ? <p className="py-6 text-center text-muted-foreground text-sm">{t("noMatch")}</p> : null}
      {groups.map(([group, facts]) => (
        <section key={group} aria-label={t(`kinds.${group}`)} className="flex flex-col gap-1">
          {kind === "all" ? (
            <h3 className="px-3 font-medium text-muted-foreground text-xs uppercase tracking-wide">
              {t(`kinds.${group}`)}
            </h3>
          ) : null}
          <ItemGroup>
            {facts.map((fact) => (
              <FactItem key={fact.id} fact={fact} words={words} />
            ))}
          </ItemGroup>
        </section>
      ))}
      {onMore ? (
        <Button variant="ghost" size="sm" className="self-center" onClick={onMore}>
          {t("more")}
        </Button>
      ) : null}
    </div>
  );
}
