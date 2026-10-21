"use client";

import { Copy, EllipsisVertical, Link2, Trash2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu-items";

import type { TaskDetail } from "../../domain/tasks-contract";
import { useBoardSelector } from "../../model/board-hooks";
import { useBoardCommands, useManagedByJira } from "../board-store";
import { closeTask, openTask } from "./task-address";

/**
 * «⋮» панели: дублировать (панель открывает копию), скопировать ссылку, удалить с Undo (панель закрывается, доска
 * показывает тост). Задача, открытая по ссылке не со своей доски, умеет только ссылку.
 */
export function PanelMenu({ detail }: { detail: TaskDetail }) {
  const t = useTranslations("kanbanPanel");
  const tk = useTranslations("kanban");
  const tc = useTranslations("common");
  const { cards } = useBoardCommands();
  const managedByJira = useManagedByJira();
  const onBoard = useBoardSelector((s) => s.cards[detail.id] !== undefined);
  const duplicable = onBoard && !managedByJira && detail.space === null && detail.jira === null;
  const deletable = onBoard && detail.can_delete && !managedByJira;

  const duplicate = () => void cards.duplicateCard(detail.id).then((copy) => (copy ? openTask(copy) : undefined));
  const remove = () => {
    closeTask();
    cards.deleteCards([detail.id], tk("commands.deleted", { title: detail.title }));
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={t("menu.label")} className="shrink-0">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-max min-w-48 max-w-72">
        <DropdownMenuGroup>
          {duplicable ? (
            <DropdownMenuItem onSelect={duplicate}>
              <Copy />
              {tc("actions.duplicate")}
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem onSelect={() => cards.copyLink(detail.id, detail.jira)}>
            <Link2 />
            {tc("actions.copyLink")}
          </DropdownMenuItem>
        </DropdownMenuGroup>
        {deletable ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem variant="destructive" onSelect={remove}>
                <Trash2 />
                {tk("taskMenu.delete")}
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
