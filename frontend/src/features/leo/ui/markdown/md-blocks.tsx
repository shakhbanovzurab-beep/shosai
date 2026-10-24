"use client";

import { cn } from "cn";

import { Separator } from "@/components/ui/separator";

import type { MdAlign, MdBlock } from "../../domain/markdown";
import { MdInlines } from "./md-inline";

// Заголовки ответа — внутри панели с заголовком Leo (h2): самый крупный из них — h3.
const HEADINGS = ["h3", "h4", "h5", "h6"] as const;
const ALIGN: Record<NonNullable<MdAlign>, string> = { left: "text-start", center: "text-center", right: "text-end" };

export function MdBlocks({ blocks }: { readonly blocks: readonly MdBlock[] }) {
  return blocks.map((block) => <MdBlockNode key={block.key} block={block} />);
}

function MdBlockNode({ block }: { readonly block: MdBlock }) {
  switch (block.type) {
    case "paragraph":
      return (
        <p dir="auto">
          <MdInlines nodes={block.children} />
        </p>
      );
    case "heading": {
      const Heading = HEADINGS[Math.min(block.depth, HEADINGS.length) - 1];
      return (
        <Heading dir="auto" className="font-semibold">
          <MdInlines nodes={block.children} />
        </Heading>
      );
    }
    case "code":
      return (
        <pre dir="ltr" className="overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs leading-relaxed">
          <code data-language={block.lang || undefined}>{block.text}</code>
        </pre>
      );
    case "quote":
      return (
        <blockquote className="flex flex-col gap-2 border-s-2 ps-3 text-muted-foreground">
          <MdBlocks blocks={block.blocks} />
        </blockquote>
      );
    case "list":
      return <MdList block={block} />;
    case "table":
      return <MdTable block={block} />;
    case "rule":
      return <Separator />;
  }
}

function MdList({ block }: { readonly block: Extract<MdBlock, { type: "list" }> }) {
  // Пункт остаётся элементом списка (не flex): иначе браузер не рисует его маркер.
  const items = block.items.map((item) => (
    <li key={item.key} className="ps-1 [&+li]:mt-1">
      <div className="flex flex-col gap-1">
        <MdBlocks blocks={item.blocks} />
      </div>
    </li>
  ));
  return block.ordered ? (
    <ol start={block.start} className="list-decimal ps-5">
      {items}
    </ol>
  ) : (
    <ul className="list-disc ps-5">{items}</ul>
  );
}

function MdTable({ block }: { readonly block: Extract<MdBlock, { type: "table" }> }) {
  const align = (index: number) => {
    const side = block.align[index] ?? null;
    return side === null ? "text-start" : ALIGN[side];
  };
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-xs">
        <thead className="bg-muted/50">
          <tr>
            {block.header.map((cell, column) => (
              <th key={cell.key} scope="col" dir="auto" className={cn("px-2 py-1.5 font-medium", align(column))}>
                <MdInlines nodes={cell.nodes} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row) => (
            <tr key={row.key} className="border-t">
              {row.cells.map((cell, column) => (
                <td key={cell.key} dir="auto" className={cn("px-2 py-1.5", align(column))}>
                  <MdInlines nodes={cell.nodes} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
