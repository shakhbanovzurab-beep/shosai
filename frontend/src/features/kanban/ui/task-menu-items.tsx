"use client";

import { useRouter } from "next/navigation";

import {
  ArrowDownToLine,
  ArrowUpToLine,
  Check,
  Columns3,
  Copy,
  ExternalLink,
  Flag,
  Link2,
  Pencil,
  Trash2,
} from "lucide-react";
import { useTranslations } from "next-intl";

import type { MenuKit } from "@/components/menu-kit";

import { TASK_PRIORITIES, type Task } from "../domain/board";
import { useBoard } from "./board-store";
import { PRIORITY_KEYS } from "./priority-keys";

/** Everything you can do to a task, for either the right-click menu or the "⋮" dropdown. */
export function TaskMenuItems({ kit: K, task, columnId }: { kit: MenuKit; task: Task; columnId: string }) {
  const { columnOrder, columnTitle, actions, editable, managedByJira } = useBoard();
  const router = useRouter();
  const t = useTranslations("kanban");
  const tc = useTranslations("common");

  return (
    <>
      <K.Group>
        {task.jira ? (
          <K.Item onSelect={() => window.open(task.jira?.url, "_blank", "noopener,noreferrer")}>
            <ExternalLink className="rtl:-scale-x-100" />
            {t("taskMenu.openInJira", { key: task.jira.key })}
          </K.Item>
        ) : null}
        {task.workspace ? (
          <K.Item onSelect={() => router.push(task.workspace?.url ?? "/app/w")}>
            <ExternalLink className="rtl:-scale-x-100" />
            {t("taskMenu.openInWorkspace", { workspace: task.workspace.workspace_name })}
          </K.Item>
        ) : null}
        <K.Item disabled={!editable} onSelect={() => actions.renameTask(task.id)}>
          <Pencil />
          {tc("actions.renameMenu")}
        </K.Item>
        <K.Sub>
          <K.SubTrigger disabled={!editable}>
            <Flag />
            {t("priority.label")}
          </K.SubTrigger>
          <K.SubContent className="w-40">
            {TASK_PRIORITIES.map((priority) => (
              <K.Item key={priority} onSelect={() => actions.setPriority(task.id, priority)}>
                <Check className={task.priority === priority ? undefined : "invisible"} />
                {t(`priority.${PRIORITY_KEYS[priority]}`)}
              </K.Item>
            ))}
          </K.SubContent>
        </K.Sub>
        <K.Sub>
          <K.SubTrigger disabled={!editable} data-menu-action="move-to">
            <Columns3 />
            {t("taskMenu.moveTo")}
          </K.SubTrigger>
          <K.SubContent className="w-44">
            {columnOrder.map((id) => (
              <K.Item
                key={id}
                disabled={id === columnId}
                onSelect={() => actions.moveTask(task.id, id, "top")}
                data-target-column-id={id}
              >
                <Check className={id === columnId ? undefined : "invisible"} />
                <span dir="auto">{columnTitle(id)}</span>
              </K.Item>
            ))}
          </K.SubContent>
        </K.Sub>
        <K.Item disabled={!editable} onSelect={() => actions.moveTask(task.id, columnId, "top")}>
          <ArrowUpToLine />
          {t("taskMenu.moveToTop")}
        </K.Item>
        <K.Item disabled={!editable} onSelect={() => actions.moveTask(task.id, columnId, "bottom")}>
          <ArrowDownToLine />
          {t("taskMenu.moveToBottom")}
        </K.Item>
      </K.Group>
      <K.Separator />
      <K.Group>
        {managedByJira || task.workspace ? null : (
          <K.Item onSelect={() => actions.duplicateTask(task.id)}>
            <Copy />
            {tc("actions.duplicate")}
          </K.Item>
        )}
        <K.Item onSelect={() => actions.copyTaskLink(task.id)}>
          <Link2 />
          {tc("actions.copyLink")}
        </K.Item>
      </K.Group>
      {managedByJira || task.workspace ? null : (
        <>
          <K.Separator />
          <K.Group>
            <K.Item variant="destructive" onSelect={() => actions.deleteTask(task.id)}>
              <Trash2 />
              {t("taskMenu.delete")}
            </K.Item>
          </K.Group>
        </>
      )}
    </>
  );
}
