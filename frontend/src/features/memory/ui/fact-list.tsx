"use client";

import { useRef, useState } from "react";

import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { ItemGroup } from "@/components/ui/item";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { MEMORY_KINDS, type MemoryFact, type MemoryKind, WORDS_MAX } from "../domain/contract";
import { groupByKind } from "../domain/facts";
import type { MemoryWords } from "../model/fact-actions";
import { setFactsQuery, useFactsQuery } from "../model/facts-resource";
import { FactItem } from "./fact-item";

// Поиск уходит на сервер, когда человек перестал печатать.
const SEARCH_PAUSE_MS = 300;
const ALL = "all";

const kindOf = (value: string): MemoryKind | null | undefined =>
  value === ALL ? null : MEMORY_KINDS.find((kind) => kind === value);

type FactListProps = {
  active: MemoryFact[];
  /** Сколько фактов во всей памяти — у «Все». */
  total: number;
  words: MemoryWords;
  /** «Показать ещё» — пока у сервера есть следующая страница. */
  onMore: (() => void) | null;
};

/** Принятые факты: вид и поиск по всей памяти на сервере, группы по видам. */
export function FactList({ active, total, words, onMore }: FactListProps) {
  const { t } = words;
  const query = useFactsQuery();
  const [text, setText] = useState(query.words);
  const pause = useRef<ReturnType<typeof setTimeout>>(undefined);
  const groups = groupByKind(active);

  const search = (next: string) => {
    setText(next);
    clearTimeout(pause.current);
    pause.current = setTimeout(() => setFactsQuery({ ...query, words: next.trim() }), SEARCH_PAUSE_MS);
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={query.kind ?? ALL}
          aria-label={t("kinds.label")}
          className="flex-wrap"
          onValueChange={(value) => {
            const kind = kindOf(value);
            if (kind !== undefined) setFactsQuery({ ...query, kind });
          }}
        >
          <ToggleGroupItem value={ALL}>
            {t("kinds.all")}
            <span className="text-muted-foreground tabular-nums">{total}</span>
          </ToggleGroupItem>
          {MEMORY_KINDS.map((kind) => (
            <ToggleGroupItem key={kind} value={kind}>
              {t(`kinds.${kind}`)}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <InputGroup className="sm:ms-auto sm:w-56">
          <InputGroupAddon>
            <Search />
          </InputGroupAddon>
          <InputGroupInput
            type="search"
            value={text}
            maxLength={WORDS_MAX}
            placeholder={t("search")}
            aria-label={t("search")}
            onChange={(event) => search(event.target.value)}
          />
        </InputGroup>
      </div>
      {active.length === 0 ? <p className="py-6 text-center text-muted-foreground text-sm">{t("noMatch")}</p> : null}
      {groups.map(([group, facts]) => (
        <section key={group} aria-label={t(`kinds.${group}`)} className="flex flex-col gap-1">
          {query.kind === null ? (
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
