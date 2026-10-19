"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Item, ItemActions, ItemContent, ItemDescription, ItemGroup, ItemTitle } from "@/components/ui/item";

import type { MemoryFact } from "../domain/contract";
import { acceptFact, type MemoryWords, rejectFact } from "../model/fact-actions";
import { FactMeta } from "./fact-meta";

/** «Запомнить это?»: кандидаты, которые Leo не использует, пока человек не ответит (ADR 0030). */
export function FactCandidates({ candidates, words }: { candidates: MemoryFact[]; words: MemoryWords }) {
  const { t } = words;
  if (candidates.length === 0) return null;
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>{t("candidates.title")}</CardTitle>
        <CardDescription>{t("candidates.description")}</CardDescription>
      </CardHeader>
      <CardContent>
        <ItemGroup>
          {candidates.map((fact) => (
            <Item key={fact.id} role="listitem" variant="outline" size="sm">
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
                <Button variant="ghost" size="sm" onClick={() => void rejectFact(fact, words)}>
                  {t("candidates.reject")}
                </Button>
                <Button size="sm" onClick={() => void acceptFact(fact, words)}>
                  {t("candidates.accept")}
                </Button>
              </ItemActions>
            </Item>
          ))}
        </ItemGroup>
      </CardContent>
    </Card>
  );
}
