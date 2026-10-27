"use client";

import { useState } from "react";

import { Undo2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Item, ItemActions, ItemContent, ItemGroup, ItemTitle } from "@/components/ui/item";
import type { MemoryChange, MemoryMessageReply } from "@/features/memory/domain/summary-contract";
import { undoChange } from "@/features/memory/model/summary";

/** One change the message made: what it did, the fact as it is now, and its Undo. */
function ChangeRow({ change }: { change: MemoryChange }) {
  const t = useTranslations("settingsMemory");
  const common = useTranslations("common");
  const [state, setState] = useState<"done" | "undoing" | "undone">("done");
  const undo = async () => {
    setState("undoing");
    setState((await undoChange(change, t("reply.undoFailed"))) ? "undone" : "done");
  };
  return (
    <Item role="listitem" size="sm" className="flex-nowrap">
      <ItemContent className="min-w-0">
        <ItemTitle dir="auto" className="line-clamp-none font-normal">
          {change.fact.statement}
        </ItemTitle>
      </ItemContent>
      <ItemActions>
        <Badge variant="secondary">{state === "undone" ? t("reply.undone") : t(`reply.${change.change}`)}</Badge>
        {state === "undone" ? null : (
          <Button variant="ghost" size="sm" disabled={state === "undoing"} onClick={() => void undo()}>
            <Undo2 data-icon="inline-start" className="rtl:-scale-x-100" />
            {common("actions.undo")}
          </Button>
        )}
      </ItemActions>
    </Item>
  );
}

/** Leo's answer to the box: the answer to a question and the changes, each undone in place (MM-D3). */
export function MemorySummaryReply({ reply }: { reply: MemoryMessageReply }) {
  const t = useTranslations("settingsMemory");
  const nothing = reply.answer === null && reply.changes.length === 0;
  return (
    <section
      aria-label={t("reply.label")}
      aria-live="polite"
      className="flex max-h-72 flex-col gap-3 overflow-y-auto border-t px-6 py-4"
    >
      {reply.answer ? (
        <p dir="auto" className="whitespace-pre-line text-[15px] leading-7">
          {reply.answer}
        </p>
      ) : null}
      {nothing ? <p className="text-muted-foreground text-sm">{t("reply.nothing")}</p> : null}
      {reply.changes.length > 0 ? (
        <ItemGroup>
          {reply.changes.map((change) => (
            <ChangeRow key={`${change.change}:${change.fact.id}`} change={change} />
          ))}
        </ItemGroup>
      ) : null}
    </section>
  );
}
