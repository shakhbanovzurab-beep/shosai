import { MAX_FILES_PER_UPLOAD, MAX_UPLOAD_BYTES } from "./contract";

/*
 * Загрузки, которые человек начал в этой вкладке, по строке на файл — то, что показывает панель загрузок
 * File Manager и Knowledge. Здесь только решения о строках; хранит их модель.
 */

/** Ждёт очереди, шлёт байты, сохраняется как файл, готов — или отклонён до начала, или сорвался в пути. */
export type UploadStatus = "waiting" | "sending" | "saving" | "done" | "failed" | "refused";

/** Почему выбранный файл не пошёл: пустой, больше допустимого, сверх одной загрузки или Leo его не прочтёт. */
export type Refusal = "empty" | "tooLarge" | "tooMany" | "unreadable";

export type UploadRow = {
  id: string;
  name: string;
  size: number;
  /** Сколько байт уже дошло до бакета. */
  sent: number;
  status: UploadStatus;
  /** Файл для Leo (загружен из Knowledge). */
  leo: boolean;
  /** Сколько ещё ждать, мс, по скорости с начала отправки; null, пока это не сказать. */
  msLeft: number | null;
  refusal: Refusal | null;
  /** Причина срыва для `failed`; слова для неё выбирает интерфейс. */
  error: unknown;
};

const FINISHED: ReadonlySet<UploadStatus> = new Set(["done", "failed", "refused"]);

/** Строка больше не изменится сама: её можно убрать из списка, не прерывая загрузку. */
export const isFinished = (row: Pick<UploadRow, "status">) => FINISHED.has(row.status);

function refusalOf(size: number, accepted: number, readable: boolean): Refusal | null {
  if (size === 0) return "empty";
  if (!readable) return "unreadable";
  if (size > MAX_UPLOAD_BYTES) return "tooLarge";
  if (accepted >= MAX_FILES_PER_UPLOAD) return "tooMany";
  return null;
}

/**
 * Делит выбор на файлы, которые пойдут, и отказы с причиной. `readable` сужает выбор до того, что читает Leo;
 * его проверка идёт раньше размера, чтобы файл для Leo не получил чужой лимит в 2 ГБ.
 */
export function screenFiles<T extends { name: string; size: number }>(
  files: readonly T[],
  readable: (file: T) => boolean = () => true,
) {
  const accepted: T[] = [];
  const refused: { file: T; refusal: Refusal }[] = [];
  for (const file of files) {
    const refusal = refusalOf(file.size, accepted.length, readable(file));
    if (refusal) refused.push({ file, refusal });
    else accepted.push(file);
  }
  return { accepted, refused };
}

/** Оставшееся время по средней скорости с начала отправки; null в первую секунду и до первого байта. */
export function timeLeft(sent: number, size: number, startedAt: number, now: number): number | null {
  const elapsed = now - startedAt;
  if (sent <= 0 || elapsed < 1_000) return null;
  return Math.max(0, ((size - sent) / sent) * elapsed);
}

/** Шапка панели: сколько файлов в пути и процент их байт, сколько готово, сколько не загрузилось. */
export function traySummary(rows: readonly UploadRow[]) {
  let active = 0;
  let done = 0;
  let failed = 0;
  let total = 0;
  let sent = 0;
  for (const row of rows) {
    if (row.status === "done") done++;
    else if (row.status === "failed" || row.status === "refused") failed++;
    else {
      active++;
      total += row.size;
      sent += Math.min(row.sent, row.size);
    }
  }
  return { active, done, failed, percent: total === 0 ? 0 : Math.floor((sent / total) * 100) };
}

/** «PDF» для «report.pdf»; пусто, если у имени нет расширения. */
export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 && dot < name.length - 1 ? name.slice(dot + 1).toUpperCase() : "";
}
