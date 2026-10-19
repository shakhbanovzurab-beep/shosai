"use client";

import { useEffect, useSyncExternalStore } from "react";

import { isFinished, type Refusal, timeLeft, type UploadRow, type UploadStatus } from "../domain/upload-queue";

/*
 * Все загрузки этой вкладки для панелей File Manager и Knowledge, по строке на файл. Живут вне React, чтобы
 * загрузка шла, пока человек ходит по экранам. Готовая строка уходит сама через несколько секунд; отклонённая
 * или сорвавшаяся остаётся, пока человек не повторит её или не уберёт.
 */

const DONE_STAYS_MS = 4_000;
// Прогресс приходит десятки раз в секунду на каждую часть; панель перерисовывается не чаще этого.
const PROGRESS_EVERY_MS = 150;
const EMPTY: readonly UploadRow[] = [];

/** Куда идёт файл: папка (null — «Мои файлы») и сразу ли его читает Leo. */
export type UploadTarget = { folderId: string | null; leo: boolean };

type Entry = {
  row: UploadRow;
  file: File;
  target: UploadTarget;
  startedAt: number;
  controller: AbortController | null;
  /** Байты уже в бакете, но файлом загрузка ещё не стала: повтор только регистрирует её. */
  uploadId: string | null;
};

const entries = new Map<string, Entry>();
const listeners = new Set<() => void>();
let snapshot = EMPTY;
let progressTimer: ReturnType<typeof setTimeout> | null = null;
// По отметке на каждую панель на экране: пока есть хоть одна, исход загрузки виден в панели.
const trays = new Set<symbol>();

function emit() {
  if (progressTimer !== null) clearTimeout(progressTimer);
  progressTimer = null;
  snapshot = [...entries.values()].map((entry) => entry.row);
  for (const listener of listeners) listener();
}

function patch(entry: Entry, change: Partial<UploadRow>, soon = false) {
  entry.row = { ...entry.row, ...change };
  if (!soon) emit();
  else progressTimer ??= setTimeout(emit, PROGRESS_EVERY_MS);
}

function addRow(file: File, target: UploadTarget, status: UploadStatus, refusal: Refusal | null) {
  const id = crypto.randomUUID();
  const row: UploadRow = {
    id,
    name: file.name,
    size: file.size,
    sent: 0,
    status,
    leo: target.leo,
    msLeft: null,
    refusal,
    error: null,
  };
  entries.set(id, { row, file, target, startedAt: 0, controller: null, uploadId: null });
  emit();
  return id;
}

function removeIfDone(id: string) {
  if (entries.get(id)?.row.status !== "done") return;
  entries.delete(id);
  emit();
}

export const uploadQueue = {
  rows: () => snapshot,
  /** Новая строка в очереди; её id ведёт строку до конца. */
  add: (file: File, target: UploadTarget) => addRow(file, target, "waiting", null),
  refuse: (file: File, target: UploadTarget, refusal: Refusal) => void addRow(file, target, "refused", refusal),
  /** Начинает отправку; сигнал прерывается, если человек её отменит. Null — строку убрали, пока она ждала. */
  start(id: string): { file: File; signal: AbortSignal } | null {
    const entry = entries.get(id);
    if (!entry) return null;
    entry.controller = new AbortController();
    entry.startedAt = Date.now();
    patch(entry, { status: "sending", sent: 0, msLeft: null, error: null });
    return { file: entry.file, signal: entry.controller.signal };
  },
  sent(id: string, bytes: number) {
    const entry = entries.get(id);
    if (!entry) return;
    patch(entry, { sent: bytes, msLeft: timeLeft(bytes, entry.row.size, entry.startedAt, Date.now()) }, true);
  },
  /** Байты дошли: загрузка регистрируется как файл. */
  saving(id: string, uploadId: string) {
    const entry = entries.get(id);
    if (!entry) return;
    entry.uploadId = uploadId;
    entry.controller = null;
    patch(entry, { status: "saving", sent: entry.row.size, msLeft: null, error: null });
  },
  done(id: string) {
    const entry = entries.get(id);
    if (!entry) return;
    entry.uploadId = null;
    patch(entry, { status: "done" });
    setTimeout(() => removeIfDone(id), DONE_STAYS_MS);
  },
  /** `uploadGone`: готовой загрузки больше нет, и повтор отправит байты заново. */
  fail(id: string, error: unknown, uploadGone: boolean) {
    const entry = entries.get(id);
    if (!entry) return;
    if (uploadGone) entry.uploadId = null;
    entry.controller = null;
    patch(entry, { status: "failed", error, msLeft: null });
  },
  /** Что нужно повтору: файл, куда он шёл, и готовая загрузка, если байты уже в бакете. */
  retryOf(id: string): { name: string; target: UploadTarget; uploadId: string | null } | null {
    const entry = entries.get(id);
    return entry?.row.status === "failed"
      ? { name: entry.row.name, target: entry.target, uploadId: entry.uploadId }
      : null;
  },
  /** Убирает строку; идущая загрузка при этом отменяется. */
  remove(id: string) {
    entries.get(id)?.controller?.abort();
    entries.delete(id);
    emit();
  },
  clearFinished() {
    for (const [id, entry] of entries) if (isFinished(entry.row)) entries.delete(id);
    emit();
  },
};

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

export const useUploadRows = () => useSyncExternalStore(subscribe, uploadQueue.rows, () => EMPTY);

/** Отмечает панель на экране: пока она есть, исход загрузки виден в ней, и тосты молчат. */
export function useUploadTrayPresence() {
  useEffect(() => {
    const tray = Symbol("upload tray");
    trays.add(tray);
    return () => {
      trays.delete(tray);
    };
  }, []);
}

export const isTrayShown = () => trays.size > 0;
