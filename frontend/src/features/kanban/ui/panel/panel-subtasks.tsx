"use client";

import { useId, useState } from "react";

import { DragDropProvider } from "@dnd-kit/react";
import { Plus } from "lucide-react";
import { useTranslations } from "use-intl";

import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Progress } from "@/components/ui/progress";

import { SUBTASKS_MAX, type Subtask, TITLE_MAX } from "../../domain/tasks-contract";
import { useSubtaskDrag } from "./subtask-drag";
import { SubtaskRow } from "./subtask-row";
import { useSubtaskActions } from "./use-panel-actions";

/** Строка «Добавить подзадачу»: после Enter остаётся открытой для следующей. */
function AddSubtask({ full, onAdd }: { full: boolean; onAdd: (title: string) => void }) {
  const t = useTranslations("kanbanPanel");
  const [title, setTitle] = useState("");
  const hintId = useId();
  return (
    <div className="flex flex-col gap-1">
      <InputGroup>
        <InputGroupAddon>
          <Plus />
        </InputGroupAddon>
        <InputGroupInput
          value={title}
          disabled={full}
          maxLength={TITLE_MAX}
          dir="auto"
          placeholder={t("subtasks.add")}
          aria-label={t("subtasks.add")}
          aria-describedby={full ? hintId : undefined}
          onChange={(event) => setTitle(event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            const next = title.trim().replace(/\s+/g, " ");
            if (!next) return;
            onAdd(next);
            setTitle("");
          }}
        />
      </InputGroup>
      {full ? (
        <p id={hintId} className="text-muted-foreground text-xs">
          {t("subtasks.full", { max: SUBTASKS_MAX })}
        </p>
      ) : null}
    </div>
  );
}

/** Подзадачи: прогресс, список с перестановкой мышью и клавиатурой, строка добавления. */
export function PanelSubtasks({
  taskId,
  subtasks,
  editable,
}: {
  taskId: string;
  subtasks: Subtask[];
  editable: boolean;
}) {
  const t = useTranslations("kanbanPanel");
  const actions = useSubtaskActions(taskId);
  const drag = useSubtaskDrag(subtasks, (subtaskId, to) => void actions.move(subtaskId, to));
  const headingId = useId();
  const done = subtasks.filter((subtask) => subtask.done).length;
  const progress = t("subtasks.progress", { done, total: subtasks.length });

  if (subtasks.length === 0 && !editable) return null;
  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <h3 id={headingId} className="font-medium text-sm">
          {t("subtasks.label")}
        </h3>
        {subtasks.length > 0 ? <span className="text-muted-foreground text-xs tabular-nums">{progress}</span> : null}
      </div>
      {subtasks.length > 0 ? (
        <Progress value={(done / subtasks.length) * 100} aria-label={progress} className="h-1" />
      ) : null}
      <DragDropProvider plugins={drag.plugins} sensors={drag.sensors} onDragEnd={drag.onDragEnd}>
        <ul className="flex flex-col">
          {subtasks.map((subtask, index) => (
            <SubtaskRow key={subtask.id} subtask={subtask} index={index} editable={editable} actions={actions} />
          ))}
        </ul>
      </DragDropProvider>
      {editable ? (
        <AddSubtask full={subtasks.length >= SUBTASKS_MAX} onAdd={(title) => void actions.add(title)} />
      ) : null}
    </section>
  );
}
