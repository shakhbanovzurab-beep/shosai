import { PartFailedError, putPart, type UploadAnswer, uploadsApi } from "../api/uploads-api";
import { type PartLink, partRanges } from "../domain/upload-parts";

/*
 * One file's upload straight to the home's bucket (FL-D1): the server signs every part for its exact length,
 * the browser PUTs the parts three at a time, and the server assembles them. A part that fails is sent again
 * with a fresh link — a dropped connection or an expired signature costs that part, not the file. An upload
 * that fails for good is cancelled, so its reserved bytes come back at once.
 */

const PART_CONCURRENCY = 3;
const PART_ATTEMPTS = 4;
const RETRY_MS = 1_000;

export type UploadPorts = {
  create: (file: File) => Promise<UploadAnswer>;
  read: (id: string) => Promise<UploadAnswer>;
  complete: (id: string) => Promise<UploadAnswer>;
  cancel: (id: string) => Promise<void>;
  put: (link: PartLink, body: Blob, onSent: (bytes: number) => void, signal?: AbortSignal) => Promise<void>;
  wait: (ms: number) => Promise<void>;
};

/** The server found the assembled file differs from the size it was told: the upload is rejected. */
export class UploadRejectedError extends Error {
  constructor() {
    super("upload rejected");
    this.name = "UploadRejectedError";
  }
}

export const browserUploadPorts: UploadPorts = {
  ...uploadsApi,
  put: putPart,
  wait: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
};

/** Runs `work` over `items`, at most `limit` at a time; the first failure fails the whole run. */
export async function runLimited<T>(items: readonly T[], limit: number, work: (item: T) => Promise<void>) {
  const queue = [...items];
  const worker = async () => {
    for (let item = queue.shift(); item !== undefined; item = queue.shift()) await work(item);
  };
  await Promise.all(Array.from({ length: Math.min(limit, queue.length) }, worker));
}

/**
 * Uploads `file`; reports the bytes sent so far and answers the ready upload's id for `register`.
 * Отмена через `signal` обрывает части в пути без повторов и отменяет загрузку на сервере.
 */
export async function uploadFile(
  file: File,
  ports: UploadPorts,
  onSent: (bytes: number) => void,
  signal?: AbortSignal,
): Promise<string> {
  const created = await ports.create(file);
  const ranges = partRanges(created.parts);
  const links = new Map(created.parts.map((part) => [part.number, part]));
  const sent = new Map<number, number>();
  const report = (number: number, bytes: number) => {
    sent.set(number, bytes);
    onSent([...sent.values()].reduce((sum, value) => sum + value, 0));
  };

  async function sendPart(number: number) {
    const [start, end] = ranges.get(number) ?? [0, 0];
    for (let attempt = 1; ; attempt++) {
      // Части из очереди после отмены не уходят: уже отменённый сигнал не шлёт события abort.
      signal?.throwIfAborted();
      const link = links.get(number);
      if (!link) return;
      try {
        await ports.put(link, file.slice(start, end), (bytes) => report(number, bytes), signal);
        return;
      } catch (error) {
        report(number, 0);
        signal?.throwIfAborted();
        if (!(error instanceof PartFailedError) || attempt >= PART_ATTEMPTS) throw error;
        await ports.wait(RETRY_MS * attempt);
        signal?.throwIfAborted();
        // Свежие ссылки на недошедшие части: так загрузка продолжается, а не начинается заново.
        const fresh = await ports.read(created.id);
        if (fresh.done_parts.includes(number)) return report(number, end - start);
        for (const part of fresh.parts) links.set(part.number, part);
      }
    }
  }

  try {
    signal?.throwIfAborted();
    const done = new Set(created.done_parts);
    const pending = created.parts.map((part) => part.number).filter((n) => !done.has(n));
    await runLimited(pending, PART_CONCURRENCY, sendPart);
    const assembled = await ports.complete(created.id);
    if (assembled.state !== "ready") throw new UploadRejectedError();
    return created.id;
  } catch (error) {
    // Отмена сразу возвращает зарезервированное место; не дошедшая отмена — забота обхода через сутки.
    await ports.cancel(created.id).catch(() => undefined);
    throw error;
  }
}
