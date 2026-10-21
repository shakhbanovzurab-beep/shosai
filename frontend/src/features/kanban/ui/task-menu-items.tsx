"use client";

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
import { useTranslations } from "use-intl";

import type { MenuKit } from "@/components/menu-kit";
import { useRouter } from "@/lib/navigation";

import { PRIORITIES, type Priority } from "../domain/tasks-contract";
import { useCard, useColumn, useColumnOrder } from "../model/board-hooks";
import { useBoardCommands, useEditable, useManagedByJira } from "./board-store";

const PRIORITY_CHOICES: (Priority | null)[] = [...PRIORITIES, null];

/** Название колонки в подменю «Переместить в». */
function ColumnName({ columnId }: { columnId: string }) {
  return <span dir="auto">{useColumn(columnId)?.title ?? ""}</span>;
}

/** Всё, что можно сделать с задачей, — для меню правой кнопки и для «⋮». */
export function TaskMenuItems({ kit: K, taskId, columnId }: { kit: MenuKit; taskId: string; columnId: string }) {
  const task = useCard(taskId);
  const columnOrder = useColumnOrder();
  const editable = useEditable();
  const managedByJira = useManagedByJira();
  const { cards: actions } = useBoardCommands();
  const router = useRouter();
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  if (!task) return null;
  const deletable = task.can_delete && !managedByJira;

  return (
    <>
      <K.Group>
        {task.jira ? (
          <K.Item onSelect={() => window.open(task.jira?.url, "_blank", "noopener,noreferrer")}>
            <ExternalLink className="rtl:-scale-x-100" />
            {t("taskMenu.openInJira", { key: task.jira.key })}
          </K.Item>
        ) : null}
        {task.space ? (
          <K.Item onSelect={() => router.push(`/app/w/${encodeURIComponent(task.space?.workspace_slug ?? "")}/tasks`)}>
            <ExternalLink className="rtl:-scale-x-100" />
            {t("taskMenu.openInWorkspace", { workspace: task.space.workspace_name })}
          </K.Item>
        ) : null}
        <K.Item disabled={!editable} onSelect={() => actions.renameCard(taskId)}>
          <Pencil />
          {tc("actions.renameMenu")}
        </K.Item>
        <K.Sub>
          <K.SubTrigger disabled={!editable}>
            <Flag />
            {t("priority.label")}
          </K.SubTrigger>
          <K.SubContent className="w-40">
            {PRIORITY_CHOICES.map((priority) => (
              <K.Item key={priority ?? "none"} onSelect={() => actions.setPriority(taskId, priority)}>
                <Check className={task.priority === priority ? undefined : "invisible"} />
                {t(`priority.${priority ?? "none"}`)}
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
                onSelect={() => actions.moveToEdge(taskId, id, "top")}
                data-target-column-id={id}
              >
                <Check className={id === columnId ? undefined : "invisible"} />
                <ColumnName columnId={id} />
              </K.Item>
            ))}
          </K.SubContent>
        </K.Sub>
        <K.Item disabled={!editable} onSelect={() => actions.moveToEdge(taskId, columnId, "top")}>
          <ArrowUpToLine />
          {t("taskMenu.moveToTop")}
        </K.Item>
        <K.Item disabled={!editable} onSelect={() => actions.moveToEdge(taskId, columnId, "bottom")}>
          <ArrowDownToLine />
          {t("taskMenu.moveToBottom")}
        </K.Item>
      </K.Group>
      <K.Separator />
      <K.Group>
        {managedByJira || task.space ? null : (
          <K.Item onSelect={() => actions.duplicateCard(taskId)}>
            <Copy />
            {tc("actions.duplicate")}
          </K.Item>
        )}
        <K.Item onSelect={() => actions.copyLink(taskId)}>
          <Link2 />
          {tc("actions.copyLink")}
        </K.Item>
      </K.Group>
      {deletable ? (
        <>
          <K.Separator />
          <K.Group>
            <K.Item
              variant="destructive"
              onSelect={() => actions.deleteCards([taskId], t("commands.deleted", { title: task.title }))}
            >
              <Trash2 />
              {t("taskMenu.delete")}
            </K.Item>
          </K.Group>
        </>
      ) : null}
    </>
  );
}
