"use client";

import type { ReactNode } from "react";

import { MoreVertical } from "lucide-react";

import { contextKit, dropdownKit, type MenuKit } from "@/components/menu-kit";
import { Button } from "@/components/ui/button";
import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

import type { Task } from "../domain/board";
import { ColumnMenuItems } from "./column-menu-items";
import { TaskMenuItems } from "./task-menu-items";

export type BoardMenuTarget = { kind: "task"; task: Task; columnId: string } | { kind: "column"; columnId: string };

const items = (target: BoardMenuTarget, kit: MenuKit) =>
  target.kind === "task" ? (
    <TaskMenuItems kit={kit} task={target.task} columnId={target.columnId} />
  ) : (
    <ColumnMenuItems kit={kit} columnId={target.columnId} />
  );

/** The "⋮" button: the same actions as the right-click menu, for touch and keyboard users. */
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
      <DropdownMenuContent className="w-52" align="end">
        {items(target, dropdownKit)}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Right-click (or long-press) anywhere on `children` to open the task's or column's menu. */
export function BoardContextMenu({ target, children }: { target: BoardMenuTarget; children: ReactNode }) {
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent className="w-52">{items(target, contextKit)}</ContextMenuContent>
    </ContextMenu>
  );
}
