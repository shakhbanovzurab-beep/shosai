"use client";

import { memo, useState } from "react";

import { cn } from "cn";

import { type MdDocument, type MdPart, parsed } from "../../domain/markdown-stream";
import { MdBlocks } from "./md-blocks";

/*
 * Ответ Leo в Markdown (ADR 0068 AG-D6): сырой HTML модели не рисуется, ссылки — только безопасные, ничего
 * внешнего не загружается. Пока ответ пишется, разбирается только его последний блок, а готовые блоки — те же
 * объекты и не перерисовываются: длинный ответ не замедляет ввод.
 */

/** Как отметить блок, пока человек смотрит на источник: подтверждающий его или остальной. */
export type PartMark = (part: MdPart) => "lit" | "dim" | null;

const Part = memo(function Part({ part, mark }: { readonly part: MdPart; readonly mark: "lit" | "dim" | null }) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-sm transition-colors",
        mark === "lit" && "bg-primary/10",
        mark === "dim" && "text-muted-foreground",
      )}
    >
      <MdBlocks blocks={part.blocks} />
    </div>
  );
});

export function LeoMarkdown({ text, mark }: { readonly text: string; readonly mark?: PartMark }) {
  const [document, setDocument] = useState<MdDocument>(() => parsed(text, null));
  const current = document.text === text ? document : parsed(text, document);
  if (current !== document) setDocument(current);
  return (
    <div className="flex flex-col gap-3">
      {current.parts.map((part) =>
        part.blocks.length === 0 ? null : <Part key={part.key} part={part} mark={mark ? mark(part) : null} />,
      )}
    </div>
  );
}
