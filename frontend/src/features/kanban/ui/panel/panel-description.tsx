"use client";

import { useTranslations } from "use-intl";

import { Skeleton } from "@/components/ui/skeleton";
import { useAutosave } from "@/hooks/use-autosave";
import { lazyComponent } from "@/lib/lazy-component";

import { DESCRIPTION_MAX } from "../../domain/tasks-contract";
import { usePanelActions } from "./use-panel-actions";

// Редактор — самая тяжёлая часть панели: грузится отдельным куском, когда панель его показывает.
const MarkdownEditor = lazyComponent(
  () => import("@/components/markdown-editor/markdown-editor").then((module) => module.MarkdownEditor),
  { loading: () => <Skeleton className="h-24 w-full" /> },
);

/** Описание задачи в Markdown: сохраняется паузой после ввода, при уходе из поля и по ⌘S. */
export function PanelDescription({ taskId, markdown }: { taskId: string; markdown: string }) {
  const t = useTranslations("kanbanPanel");
  const actions = usePanelActions(taskId);
  const autosave = useAutosave(async (text) => {
    // Сбой уже назван тостом и вернул прежний текст в панели; здесь его нужно только не потерять.
    if (!(await actions.patch({ description: text.slice(0, DESCRIPTION_MAX) })))
      throw new Error("description not saved");
  }, 800);
  return (
    <section aria-label={t("description.label")} className="flex flex-col gap-2">
      <h3 className="font-medium text-sm">{t("description.label")}</h3>
      <div className="rounded-lg border px-3 py-2 focus-within:border-ring">
        <MarkdownEditor
          initialMarkdown={markdown}
          onChange={autosave.schedule}
          onFlush={autosave.flush}
          label={t("description.label")}
          placeholder={t("description.placeholder")}
          minHeight="min-h-20"
        />
      </div>
    </section>
  );
}

/** Описание только для чтения — у задачи Jira, где его меняют в Jira. */
export function ReadOnlyDescription({ text }: { text: string }) {
  const t = useTranslations("kanbanPanel");
  if (!text) return null;
  return (
    <section aria-label={t("description.label")} className="flex flex-col gap-2">
      <h3 className="font-medium text-sm">{t("description.label")}</h3>
      <p dir="auto" className="whitespace-pre-wrap text-sm leading-relaxed">
        {text}
      </p>
    </section>
  );
}
