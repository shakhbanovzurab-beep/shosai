"use client";

import { cn } from "cn";

import type { DiffRow } from "../domain/config-diff";

function DiffCell({ text, tone }: { text: string | null; tone: "same" | "removed" | "added" }) {
  return (
    <div
      className={cn(
        "min-h-5 whitespace-pre-wrap break-words px-2 font-mono text-xs leading-5",
        tone === "removed" && text !== null && "bg-destructive/10 text-destructive",
        tone === "added" && text !== null && "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
        text === null && "bg-muted/40",
      )}
    >
      {text === null ? null : (
        <>
          {tone === "same" ? null : <span className="sr-only">{tone === "removed" ? "Удалено: " : "Добавлено: "}</span>}
          {text === "" ? " " : text}
        </>
      )}
    </div>
  );
}

/** Построчное сравнение бок о бок: слева удалённое, справа добавленное. */
export function DiffTable({ rows, changesOnly }: { rows: DiffRow[]; changesOnly: boolean }) {
  const visible = rows
    .map((row, index) => ({ row, line: index + 1 }))
    .filter(({ row }) => !changesOnly || row.kind === "changed");

  if (visible.length === 0) {
    return <p className="p-6 text-center text-muted-foreground text-sm">Различий нет — конфигурации совпадают.</p>;
  }

  return (
    <div className="grid grid-cols-2 divide-x">
      {visible.map(({ row, line }) => (
        <div key={line} className="contents">
          <DiffCell text={row.left} tone={row.kind === "same" ? "same" : "removed"} />
          <DiffCell text={row.right} tone={row.kind === "same" ? "same" : "added"} />
        </div>
      ))}
    </div>
  );
}
