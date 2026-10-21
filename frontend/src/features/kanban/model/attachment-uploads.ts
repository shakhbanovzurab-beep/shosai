"use client";

import { useSyncExternalStore } from "react";

import type { FileItem } from "@/features/file-manager/domain/contract";
import { runLimited, uploadFile } from "@/lib/uploads/upload-file";

import { taskAttachmentPorts } from "../api/attachment-uploads-api";
import { tasksApi } from "../api/tasks-api";
import { type KanbanProblem, kanbanProblemOf } from "../domain/problems";
import { ATTACHMENT_UPLOAD_MAX, type Attachment } from "../domain/tasks-contract";
import type { BoardStore } from "./board-store";
import { showTask } from "./task-sync";

/*
 * Вложения в пути: загрузка с ходом или копия файла из File Manager (FL-D4). Строка живёт, пока вложение не встало
 * в задачу; отказ остаётся строкой с причиной, пока человек её не уберёт. Закрытая панель загрузку не обрывает.
 */

/** Почему не вышло: известный код или ошибка как есть (её текст и id запроса покажет панель). */
export type AttachFailure = KanbanProblem | { error: unknown };

export type AttachmentRow = {
  id: string;
  /** Загрузка с компьютера (с ходом) или копия из File Manager (без передачи байтов). */
  kind: "upload" | "copy";
  name: string;
  size: number;
  sent: number;
  failure: AttachFailure | null;
};

const FILES_AT_ONCE = 2;
const NONE: AttachmentRow[] = [];
const rows = new Map<string, AttachmentRow[]>();
const aborts = new Map<string, AbortController>();
const listeners = new Set<() => void>();

function set(taskId: string, change: (list: AttachmentRow[]) => AttachmentRow[]) {
  const next = change(rows.get(taskId) ?? NONE);
  if (next.length === 0) rows.delete(taskId);
  else rows.set(taskId, next);
  for (const listener of listeners) listener();
}
const patchRow = (taskId: string, rowId: string, patch: Partial<AttachmentRow>) =>
  set(taskId, (list) => list.map((row) => (row.id === rowId ? { ...row, ...patch } : row)));
const dropRow = (taskId: string, rowId: string) => set(taskId, (list) => list.filter((row) => row.id !== rowId));

const failureOf = (error: unknown): AttachFailure => kanbanProblemOf(error) ?? { error };

function added(taskId: string, store: BoardStore | null, attachment: Attachment) {
  showTask(taskId, store, (detail) =>
    detail.attachments.some((item) => item.id === attachment.id)
      ? detail
      : { ...detail, attachments: [...detail.attachments, attachment] },
  );
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** Строки вложений этой задачи, которые ещё в пути или не прошли. */
export const attachmentRows = (taskId: string) => rows.get(taskId) ?? NONE;

export const useAttachmentRows = (taskId: string) =>
  useSyncExternalStore(
    subscribe,
    () => attachmentRows(taskId),
    () => NONE,
  );

/** Загрузить файлы с компьютера; слишком большой отказан сразу, без передачи байтов. */
export function attachFiles(taskId: string, files: File[], workspaceId: string | null, store: BoardStore | null) {
  const started = files.map((file) => ({
    file,
    row: { id: crypto.randomUUID(), kind: "upload" as const, name: file.name, size: file.size, sent: 0, failure: null },
  }));
  set(taskId, (list) => [
    ...list,
    ...started.map(({ file, row }) =>
      file.size > ATTACHMENT_UPLOAD_MAX ? { ...row, failure: "upload_too_large" as const } : row,
    ),
  ]);
  const ports = taskAttachmentPorts(workspaceId);
  const work = async ({ file, row }: (typeof started)[number]) => {
    const controller = new AbortController();
    aborts.set(row.id, controller);
    try {
      const uploadId = await uploadFile(file, ports, (sent) => patchRow(taskId, row.id, { sent }), controller.signal);
      const attachment = await tasksApi.addAttachment(taskId, { upload_id: uploadId });
      dropRow(taskId, row.id);
      added(taskId, store, attachment);
    } catch (error) {
      if (controller.signal.aborted) dropRow(taskId, row.id);
      else patchRow(taskId, row.id, { failure: failureOf(error) });
    } finally {
      aborts.delete(row.id);
    }
  };
  void runLimited(
    started.filter(({ file }) => file.size <= ATTACHMENT_UPLOAD_MAX),
    FILES_AT_ONCE,
    work,
  );
}

/** Приложить копии файлов из File Manager: байты не передаются, сервер копирует объект. */
export function attachCopies(taskId: string, files: FileItem[], store: BoardStore | null) {
  const started = files.map((file) => ({
    file,
    row: {
      id: crypto.randomUUID(),
      kind: "copy" as const,
      name: file.name,
      size: file.size_bytes,
      sent: 0,
      failure: null,
    },
  }));
  set(taskId, (list) => [...list, ...started.map(({ row }) => row)]);
  for (const { file, row } of started)
    tasksApi.addAttachment(taskId, { file_id: file.id }).then(
      (attachment) => {
        dropRow(taskId, row.id);
        added(taskId, store, attachment);
      },
      (error: unknown) => patchRow(taskId, row.id, { failure: failureOf(error) }),
    );
}

/** Оборвать загрузку: её строка уходит, байты на сервере отменяются клиентом загрузок. */
export const cancelUpload = (rowId: string) => aborts.get(rowId)?.abort();

/** Убрать строку отказа. */
export const dismissRow = (taskId: string, rowId: string) => dropRow(taskId, rowId);

/** Идёт ли эта строка ещё (загрузка или копия), а не стоит отказом. */
export const isBusy = (row: AttachmentRow) => row.failure === null;
