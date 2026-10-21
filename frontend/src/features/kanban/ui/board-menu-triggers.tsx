"use client";

import type { ReactNode } from "react";

import { MoreVertical } from "lucide-react";

import { contextKit, dropdownKit, type MenuKit } from "@/components/menu-kit";
import { Button } from "@/components/ui/button";
import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

import { ColumnMenuItems } from "./column-menu-items";
import { TaskMenuItems } from "./task-menu-items";

export type BoardMenuTarget = { kind: "task"; taskId: string; columnId: string } | { kind: "column"; columnId: string };

const items = (target: BoardMenuTarget, kit: MenuKit) =>
  target.kind === "task" ? (
    <TaskMenuItems kit={kit} taskId={target.taskId} columnId={target.columnId} />
  ) : (
    <ColumnMenuItems kit={kit} columnId={target.columnId} />
  );

/** Кнопка «⋮»: те же действия, что в меню правой кнопки, для касания и клавиатуры. */
export function BoardActionsButton({
  target,
  label,
  className,
}: {
  target: BoardMenuTarget;
  label: string;
  className?: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={label} className={className}>
          <MoreVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-max min-w-52 max-w-72" align="end">
        {items(target, dropdownKit)}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Правая кнопка (или долгое нажатие) где угодно на `children` открывает меню задачи или колонки. */
export function BoardContextMenu({ target, children }: { target: BoardMenuTarget; children: ReactNode }) {
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent className="w-max min-w-52 max-w-72">{items(target, contextKit)}</ContextMenuContent>
    </ContextMenu>
  );
}
