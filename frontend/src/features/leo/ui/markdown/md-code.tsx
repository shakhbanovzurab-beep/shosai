"use client";

import type { MdBlock } from "../../domain/markdown";
import { CopyAction } from "../leo-message-actions";
import { useHighlighter } from "./lazy-renderers";

/** Блок кода ответа: язык и «Копировать» в шапке, код с подсветкой; пока подсветка грузится — тем же текстом. */
export function MdCode({ block }: { readonly block: Extract<MdBlock, { type: "code" }> }) {
  const highlighter = useHighlighter();
  const highlighted = highlighter?.highlightedCode(block.lang, block.text) ?? null;

  return (
    <div className="overflow-hidden rounded-lg border bg-muted/40">
      <div className="flex h-8 items-center justify-between gap-2 border-b ps-3 pe-1">
        <span className="truncate font-mono text-muted-foreground text-xs">{block.lang}</span>
        <CopyAction text={block.text} />
      </div>
      <pre dir="ltr" className="overflow-x-auto p-3 font-mono text-xs leading-relaxed">
        <code data-language={block.lang || undefined}>{highlighted ?? block.text}</code>
      </pre>
    </div>
  );
}
