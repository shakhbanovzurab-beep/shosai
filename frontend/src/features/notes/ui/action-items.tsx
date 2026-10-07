"use client";

import * as React from "react";

import { cn } from "cn";

import { Checkbox } from "@/components/ui/checkbox";

import type { NoteActionItem } from "../domain/types";

export function ActionItems({ items }: { readonly items: NoteActionItem[] }) {
  const [doneIds, setDoneIds] = React.useState(() => new Set(items.filter((i) => i.done).map((i) => i.id)));

  const toggle = (id: string, done: boolean) => {
    setDoneIds((current) => {
      const next = new Set(current);
      if (done) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  return (
    <ul className="flex flex-col gap-2.5">
      {items.map((item) => {
        const isDone = doneIds.has(item.id);
        const checkboxId = `action-item-${item.id}`;
        return (
          <li key={item.id} className="flex items-start gap-3">
            <Checkbox
              id={checkboxId}
              checked={isDone}
              onCheckedChange={(checked) => toggle(item.id, checked === true)}
              className="mt-0.5"
            />
            <label htmlFor={checkboxId} className="flex min-w-0 flex-1 cursor-pointer flex-col gap-0.5 text-sm">
              <span dir="auto" className={cn(isDone && "text-muted-foreground line-through")}>
                {item.text}
              </span>
              <span dir="auto" className="text-muted-foreground text-xs">
                {item.owner}
              </span>
            </label>
          </li>
        );
      })}
    </ul>
  );
}
