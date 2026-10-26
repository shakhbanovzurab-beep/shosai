"use client";

import type { MdBlock } from "../../domain/markdown";
import { CopyAction } from "../leo-message-actions";
import { useHighlighter } from "./lazy-renderers";
import { MdDiagram } from "./md-diagram";

type CodeBlock = Extract<MdBlock, { type: "code" }>;

/** Блок кода ответа; закрытый блок `mermaid` — диаграмма, а пока он пишется — код, как модель его пишет. */
export function MdCode({ block }: { readonly block: CodeBlock }) {
  if (block.lang.toLowerCase() === "mermaid" && block.closed) {
    return (
      <MdDiagram source={block.text}>
        <CodeListing block={block} />
      </MdDiagram>
    );
  }
  return <CodeListing block={block} />;
}

/** Язык и «Копировать» в шапке, код с подсветкой; пока подсветка грузится — тем же текстом. */
function CodeListing({ block }: { readonly block: CodeBlock }) {
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
