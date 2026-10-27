"use client";

import { Button } from "@/components/ui/button";
import { Item, ItemActions, ItemContent, ItemDescription, ItemTitle } from "@/components/ui/item";

import type { MemoryFact } from "../domain/contract";
import type { MemoryWords } from "../model/fact-actions";
import { FactMeta } from "./fact-meta";

type CandidateRowProps = {
  fact: MemoryFact;
  words: MemoryWords;
  onAnswer: (remember: boolean) => void;
};

/** Кандидат с источником и ответом «Запомнить» / «Не запоминать»; Leo его не использует, пока нет ответа. */
export function CandidateRow({ fact, words, onAnswer }: CandidateRowProps) {
  const { t } = words;
  return (
    <Item role="listitem" variant="outline" size="sm">
      {/* Своя минимальная ширина: на узком экране кнопки уходят под текст, а не сжимают его. */}
      <ItemContent className="min-w-48">
        <ItemTitle dir="auto" className="line-clamp-none font-normal">
          {fact.statement}
        </ItemTitle>
        <ItemDescription className="text-xs">
          <FactMeta fact={fact} />
        </ItemDescription>
      </ItemContent>
      <ItemActions className="ms-auto">
        <Button variant="ghost" size="sm" onClick={() => onAnswer(false)}>
          {t("candidates.reject")}
        </Button>
        <Button size="sm" onClick={() => onAnswer(true)}>
          {t("candidates.accept")}
        </Button>
      </ItemActions>
    </Item>
  );
}
