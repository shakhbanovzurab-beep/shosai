"use client";

import { useSortable } from "@dnd-kit/react/sortable";
import { cn } from "cn";
import { GripVertical, X } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

import { type Subtask, TITLE_MAX } from "../../domain/tasks-contract";
import { isLocalId } from "../../model/task-sync";

type SubtaskEdits = {
  update: (subtaskId: string, patch: { done?: boolean; title?: string }) => Promise<boolean>;
  remove: (subtaskId: string, message: string) => void;
};

/** Название подзадачи правится на месте: Enter или уход из поля сохраняют, Esc возвращает прежнее. */
function SubtaskTitle({
  subtask,
  editable,
  onRename,
}: {
  subtask: Subtask;
  editable: boolean;
  onRename: (title: string) => void;
}) {
  const t = useTranslations("kanbanPanel");
  const commit = (value: string) => {
    const title = value.trim().replace(/\s+/g, " ");
    if (title && title !== subtask.title) onRename(title);
  };
  return (
    <input
      key={subtask.title}
      defaultValue={subtask.title}
      readOnly={!editable || isLocalId(subtask.id)}
      aria-label={t("subtasks.titleLabel")}
      maxLength={TITLE_MAX}
      dir="auto"
      className={cn(
        "min-w-0 flex-1 truncate rounded-sm bg-transparent px-1 py-0.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
        subtask.done && "text-muted-foreground line-through",
      )}
      onBlur={(event) => commit(event.currentTarget.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
        if (event.key === "Escape") event.currentTarget.value = subtask.title;
      }}
    />
  );
}

/** Подзадача: ручка, отметка, название, удаление. Пока она создаётся, с ней ничего не сделать. */
export function SubtaskRow({
  subtask,
  index,
  editable,
  actions,
}: {
  subtask: Subtask;
  index: number;
  editable: boolean;
  actions: SubtaskEdits;
}) {
  const t = useTranslations("kanbanPanel");
  const pending = isLocalId(subtask.id);
  const { ref, handleRef, isDragging } = useSortable({ id: subtask.id, index, disabled: !editable || pending });
  const title = subtask.title;

  return (
    <li
      ref={ref}
      aria-busy={pending || undefined}
      className={cn(
        "group/subtask flex items-center gap-1.5 rounded-md px-1 py-0.5 hover:bg-muted/50",
        isDragging && "opacity-40",
        pending && "opacity-60",
      )}
    >
      {editable ? (
        <Button
          ref={handleRef}
          variant="ghost"
          size="icon-xs"
          disabled={pending}
          aria-label={t("subtasks.move", { title })}
          className="cursor-grab text-muted-foreground active:cursor-grabbing"
        >
          <GripVertical />
        </Button>
      ) : null}
      <Checkbox
        checked={subtask.done}
        disabled={!editable || pending}
        aria-label={title}
        onCheckedChange={(checked) => void actions.update(subtask.id, { done: checked === true })}
      />
      <SubtaskTitle
        subtask={subtask}
        editable={editable}
        onRename={(next) => void actions.update(subtask.id, { title: next })}
      />
      {editable ? (
        <Button
          variant="ghost"
          size="icon-xs"
          disabled={pending}
          aria-label={t("subtasks.delete", { title })}
          className="text-muted-foreground opacity-0 pointer-coarse:opacity-100 focus-visible:opacity-100 group-hover/subtask:opacity-100"
          onClick={() => actions.remove(subtask.id, t("subtasks.deleted", { title }))}
        >
          <X />
        </Button>
      ) : null}
    </li>
  );
}
