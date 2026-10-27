"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ItemGroup } from "@/components/ui/item";

import type { MemoryFact } from "../domain/contract";
import { acceptFact, type MemoryWords, rejectFact } from "../model/fact-actions";
import { CandidateRow } from "./candidate-row";

/** «Запомнить это?»: кандидаты, которые Leo не использует, пока человек не ответит (ADR 0071 MM-D1). */
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
            <CandidateRow
              key={fact.id}
              fact={fact}
              words={words}
              onAnswer={(remember) => void (remember ? acceptFact(fact, words) : rejectFact(fact, words))}
            />
          ))}
        </ItemGroup>
      </CardContent>
    </Card>
  );
}
