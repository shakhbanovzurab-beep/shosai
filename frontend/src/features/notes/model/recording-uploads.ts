"use client";

import type { ReactNode } from "react";
import { useSyncExternalStore } from "react";

import { toast } from "sonner";

import { browserUploadPorts, runLimited, uploadFile } from "@/lib/uploads/upload-file";

import { notesApi } from "../api/notes-api";
import { refreshCounts } from "./folders";
import { reloadLibraries } from "./library-resource";
import { describeNoteError } from "./problem-words";
import type { NotesWords } from "./words";

/*
 * Загрузка записей встреч: файл идёт прямо в бакет дома тем же путём, что и файлы (FL-D1), затем
 * `POST /v1/notes/imports` забирает его, и встреча появляется в библиотеке со статусом «Расшифровывается». Строка
 * загрузки живёт, пока байты идут; отказ остаётся строкой с причиной, пока человек её не уберёт. После импорта
 * строка знает свою встречу: библиотека прячет её, как только встреча пришла, и на её месте показывает встречу.
 */

const AT_ONCE = 2;
const RECORDING_PORTS = browserUploadPorts("recording");

export interface RecordingUpload {
  readonly id: string;
  readonly name: string;
  readonly size: number;
  /** Сколько байт уже ушло в бакет. */
  readonly sent: number;
  /** Почему загрузка не вышла; null, пока она идёт. */
  readonly failed: ReactNode | null;
  /** Встреча, которой стала запись; null до импорта. */
  readonly meetingId: string | null;
}

let rows: readonly RecordingUpload[] = [];
const listeners = new Set<() => void>();
let counter = 0;

function set(next: readonly RecordingUpload[]) {
  rows = next;
  for (const listener of listeners) listener();
}

const change = (id: string, patch: Partial<RecordingUpload>) =>
  set(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));

export const useRecordingUploads = () =>
  useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => rows,
    () => rows,
  );

export const removeRecordingUpload = (id: string) => set(rows.filter((row) => row.id !== id));

async function send(file: File, id: string, t: NotesWords) {
  try {
    const uploadId = await uploadFile(file, RECORDING_PORTS, (sent) => change(id, { sent }));
    const started = await notesApi.importRecording(uploadId);
    change(id, { meetingId: started.meeting_id });
    // Строку убираем, когда библиотеки уже прочитаны с новой встречей: иначе её место на миг займёт другая.
    await reloadLibraries();
    refreshCounts();
    removeRecordingUpload(id);
  } catch (error) {
    const reason = describeNoteError(error, t);
    change(id, { failed: reason });
    toast.error(t("upload.failed", { name: file.name }), { description: reason });
  }
}

/** Ставит записи в очередь: по две за раз; каждая — своя строка с ходом загрузки. */
export function uploadRecordings(files: readonly File[], t: NotesWords) {
  const queued = files.map((file) => {
    counter += 1;
    const row: RecordingUpload = {
      id: `recording-${counter}`,
      name: file.name,
      size: file.size,
      sent: 0,
      failed: null,
      meetingId: null,
    };
    return { file, row };
  });
  set([...queued.map((item) => item.row), ...rows]);
  // send сам ловит свои сбои и показывает их строкой, поэтому очередь не обрывается на первой неудаче.
  void runLimited(queued, AT_ONCE, ({ file, row }) => send(file, row.id, t));
}

/**
 * Загрузки, которые показывает библиотека: без тех, чья встреча уже пришла, — на их месте сама встреча, в том же
 * кадре. Первая занимает слот последней встречи, если он есть у вида (`slot`).
 */
export function shownUploads(rows: readonly RecordingUpload[], items: readonly { id: string }[], slot: boolean) {
  const arrived = new Set(items.map((item) => item.id));
  const shown = rows.filter((row) => row.meetingId === null || !arrived.has(row.meetingId));
  const lead = slot ? shown.at(0) : undefined;
  return { lead, others: lead ? shown.slice(1) : shown };
}
