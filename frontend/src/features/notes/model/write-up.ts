import { useSyncExternalStore } from "react";

import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { contentApi, type WriteUpOut } from "../api/note-content-api";
import { notesApi, type RunOut } from "../api/notes-api";
import { isApiCode } from "../domain/problems";
import type { WriteUp } from "../domain/write-up";
import { refreshContent } from "./meeting-content";
import { refreshMeeting } from "./meeting-resource";
import { describeNoteError } from "./problem-words";
import type { NotesWords, TemplateWords } from "./words";

/*
 * Запись Leo о встрече и её переписывание по шаблону. Переписывание — прогон на сервере: страница ждёт его
 * конца, опрашивая прогон, и затем перечитывает запись, расшифровку и карту.
 */

const POLL_MS = 1500;
const TERMINAL: ReadonlySet<RunOut["state"]> = new Set(["succeeded", "partially_completed", "failed"]);

const writeUps = new Map<string, PollingResource<WriteUp | null>>();

/** Запись Leo из ответа сервера. */
const writeUpOf = (out: WriteUpOut): WriteUp => ({
  templateId: out.template_id,
  automatic: out.automatic,
  revision: out.revision,
  sections: out.sections.map((section) => ({
    kind: section.kind,
    headingCode: section.heading_code ?? null,
    title: section.title ?? null,
    text: section.text ?? null,
    items:
      section.items?.map((item) => ({
        id: item.id,
        text: item.text,
        ownerName: item.owner_name,
        dueOn: item.due_on,
        startMs: item.start_ms,
      })) ?? null,
  })),
});
const runs = new Map<string, PollingResource<RunOut>>();

function writeUpResource(id: string) {
  let resource = writeUps.get(id);
  if (!resource) {
    // Записи ещё нет — заметки не написаны: страница скажет об этом сама.
    resource = createPollingResource(() =>
      contentApi.writeUp(id).then(writeUpOf, (error: unknown) => {
        if (isApiCode(error, "write_up_not_found")) return null;
        throw error;
      }),
    );
    writeUps.set(id, resource);
  }
  return resource;
}

function runOf(id: string) {
  let resource = runs.get(id);
  if (!resource) {
    resource = createPollingResource(
      () => notesApi.run(id),
      (run) => !TERMINAL.has(run.state),
    );
    runs.set(id, resource);
  }
  return resource;
}

export const useWriteUp = (id: string) => usePollingResource(writeUpResource(id));
export const retryWriteUp = (id: string) => writeUpResource(id).refresh();
/** Последний прогон встречи: по нему страница говорит, что записи обновились с голосами, или почему не вышли. */
export const useRun = (runId: string) => usePollingResource(runOf(runId));

// Встречи, чья запись сейчас переписывается: меню шаблонов и запись показывают это все сразу.
const rewriting = new Set<string>();
const listeners = new Set<() => void>();
const emit = () => {
  for (const listener of listeners) listener();
};

export const useRewriting = (id: string) =>
  useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => rewriting.has(id),
    () => false,
  );

// Дольше цели заметок (p95 ≤ 10 мин) с запасом; дальше страница подхватит записи опросом самой встречи.
const WAIT_MS = 20 * 60 * 1000;

async function finished(runId: string): Promise<RunOut | null> {
  const deadline = Date.now() + WAIT_MS;
  while (Date.now() < deadline) {
    const run = await notesApi.run(runId);
    if (TERMINAL.has(run.state)) return run;
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
  return null;
}

/** Переписывает запись встречи по шаблону (или по тому же — заново) и ждёт, пока прогон закончится. */
export async function rewriteNotes(
  id: string,
  template: { id: string; name: string },
  words: { t: TemplateWords; notes: NotesWords },
  again: boolean,
) {
  if (rewriting.has(id)) return;
  rewriting.add(id);
  emit();
  try {
    const accepted = await contentApi.rewrite(id, template.id, crypto.randomUUID());
    const run = await finished(accepted.run_id);
    await Promise.all([writeUpResource(id).refresh(), refreshMeeting(id)]);
    refreshContent(id);
    if (run === null) return;
    if (run.state === "failed") toast.error(words.t("rewriteFailed"));
    else toast.success(again ? words.t("regenerated") : words.t("rewritten", { template: template.name }));
  } catch (error) {
    toast.error(describeNoteError(error, words.notes));
  } finally {
    rewriting.delete(id);
    emit();
  }
}
