import { type PartLink, partRanges } from "./upload-parts";
import { PartFailedError, putPart, type UploadAnswer, type UploadPurpose, uploadsApi } from "./uploads-api";

/*
 * Загрузка одного файла прямо в бакет дома (FL-D1): сервер подписывает каждую часть на её точную длину, браузер
 * кладёт части по три сразу, сервер собирает их. Не дошедшая часть уходит снова по свежей ссылке — оборванное
 * соединение или истёкшая подпись стоят этой части, а не файла. Загрузку, не прошедшую окончательно, отменяем,
 * чтобы зарезервированные байты вернулись сразу. Загрузками пользуются несколько срезов, каждый со своим назначением.
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

/** Сервер нашёл, что собранный файл не совпал с заявленным размером: загрузка отклонена. */
export class UploadRejectedError extends Error {
  constructor() {
    super("upload rejected");
    this.name = "UploadRejectedError";
  }
}

/** Порты браузера для загрузки с назначением `purpose`: настоящий API, бакет и таймер. */
export function browserUploadPorts(purpose: UploadPurpose): UploadPorts {
  return {
    ...uploadsApi,
    create: (file) => uploadsApi.create(file, purpose),
    put: putPart,
    wait: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  };
}

/** Выполняет `work` над `items`, не больше `limit` сразу; первая же ошибка роняет весь прогон. */
export async function runLimited<T>(items: readonly T[], limit: number, work: (item: T) => Promise<void>) {
  const queue = [...items];
  const worker = async () => {
    for (let item = queue.shift(); item !== undefined; item = queue.shift()) await work(item);
  };
  await Promise.all(Array.from({ length: Math.min(limit, queue.length) }, worker));
}

/**
 * Загружает `file`; сообщает, сколько байт уже ушло, и отвечает id готовой загрузки, чтобы срез её забрал.
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
