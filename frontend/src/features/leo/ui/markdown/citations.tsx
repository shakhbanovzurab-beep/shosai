"use client";

import { createContext, type ReactNode, use } from "react";

import { citedParts } from "../../domain/markdown-cites";

/** Как ответ рисует номер источника: панель с источниками кладёт его сюда; без неё `[n]` остаётся текстом. */
export interface Citations {
  readonly count: number;
  readonly marker: (n: number) => ReactNode;
}

export const CitationsContext = createContext<Citations | null>(null);

/** Текст ответа с маркерами источников на местах `[n]`. */
export function CitedText({ text }: { readonly text: string }) {
  const citations = use(CitationsContext);
  if (citations === null) return text;
  return citedParts(text, citations.count).map((part) =>
    "n" in part ? (
      <span key={part.key} className="whitespace-nowrap">
        {citations.marker(part.n)}
        {part.tail}
      </span>
    ) : (
      <span key={part.key}>{part.text}</span>
    ),
  );
}
