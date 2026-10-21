"use client";

import { useId } from "react";

import { useTranslations } from "use-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { TASK_STATUSES, type TaskDetail, type TaskStatus, TITLE_MAX } from "../../domain/tasks-contract";
import { useBoardSelector } from "../../model/board-hooks";
import { taskResource } from "../../model/task-resource";
import { useBoardCommands } from "../board-store";
import { PanelMenu } from "./panel-menu";
import { usePanelActions } from "./use-panel-actions";

/** Название задачи, правится на месте: Enter или уход из поля сохраняют, Esc возвращает прежнее. */
function TitleInput({ detail, editable }: { detail: TaskDetail; editable: boolean }) {
  const t = useTranslations("kanbanPanel");
  const actions = usePanelActions(detail.id);
  const commit = (value: string) => {
    const title = value.trim().replace(/\s+/g, " ");
    if (title && title !== detail.title) void actions.patch({ title });
  };
  return (
    <Textarea
      key={detail.title}
      defaultValue={detail.title}
      readOnly={!editable}
      aria-label={t("titleLabel")}
      maxLength={TITLE_MAX}
      rows={1}
      dir="auto"
      className="field-sizing-content min-h-0 resize-none border-transparent px-1 py-0.5 font-semibold text-lg shadow-none [text-align:match-parent] focus-visible:border-input md:text-lg dark:bg-transparent"
      onBlur={(event) => commit(event.currentTarget.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          event.currentTarget.blur();
        }
        if (event.key === "Escape") event.currentTarget.value = detail.title;
      }}
    />
  );
}

/** Колонка на этой доске: перенос меняет статус по виду колонки, как перетаскивание. */
function ColumnSelect({ detail, columnId, editable }: { detail: TaskDetail; columnId: string; editable: boolean }) {
  const t = useTranslations("kanbanPanel");
  const { cards } = useBoardCommands();
  const order = useBoardSelector((s) => s.columnOrder);
  const columns = useBoardSelector((s) => s.columns);
  const labelId = useId();
  return (
    <div className="flex items-center gap-2">
      <span id={labelId} className="text-muted-foreground text-sm">
        {t("column")}
      </span>
      <Select
        value={columnId}
        disabled={!editable}
        // Статус задачи меняется на сервере вместе с колонкой: панель перечитывает задачу после переноса.
        onValueChange={(next) =>
          void cards.moveToEdge(detail.id, next, "top").then(() => taskResource(detail.id).reload())
        }
      >
        <SelectTrigger size="sm" aria-labelledby={labelId} className="min-w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {order.map((id) => (
              <SelectItem key={id} value={id}>
                <span dir="auto">{columns[id]?.title}</span>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
}

/** Статус задачи, которой нет на этой доске (её открыли по ссылке). */
function StatusSelect({ detail, editable }: { detail: TaskDetail; editable: boolean }) {
  const t = useTranslations("kanbanPanel");
  const tk = useTranslations("kanban");
  const actions = usePanelActions(detail.id);
  const labelId = useId();
  return (
    <div className="flex items-center gap-2">
      <span id={labelId} className="text-muted-foreground text-sm">
        {t("status")}
      </span>
      <Select
        value={detail.status}
        disabled={!editable}
        onValueChange={(status) => void actions.patch({ status: status as TaskStatus })}
      >
        <SelectTrigger size="sm" aria-labelledby={labelId} className="min-w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {TASK_STATUSES.map((status) => (
              <SelectItem key={status} value={status}>
                {tk(`kinds.${status}`)}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
}

/** Верх панели: название с «⋮» и где задача на доске. */
export function PanelHeader({ detail, editable }: { detail: TaskDetail; editable: boolean }) {
  const columnId = useBoardSelector((s) => {
    for (const id of s.columnOrder) if (s.cardIds[id]?.includes(detail.id)) return id;
    return null;
  });
  return (
    <header className="flex flex-col gap-3 pe-8">
      <div className="flex items-start gap-1">
        <TitleInput detail={detail} editable={editable} />
        <PanelMenu detail={detail} />
      </div>
      {columnId ? (
        <ColumnSelect detail={detail} columnId={columnId} editable={editable} />
      ) : (
        <StatusSelect detail={detail} editable={editable} />
      )}
    </header>
  );
}
