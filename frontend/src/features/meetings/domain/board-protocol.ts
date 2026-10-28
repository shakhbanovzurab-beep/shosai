/*
 * Протокол доски между участниками (MR-D13, docs/meetings-api.md): правки, присутствие и догон — надёжным
 * текстовым потоком на топике `wb`, курсоры — пакетами без гарантии на `wb.cursor`. Всё, что пришло из канала,
 * недоверенно: гость по ссылке — обычный участник, поэтому кривое сообщение отбрасывается, а не роняет доску.
 */

export const BOARD_TOPIC = "wb";
export const CURSOR_TOPIC = "wb.cursor";
/** Имя видеодорожки доски во время записи: люди звонка её не смотрят — у них сама доска. */
export const BOARD_TRACK = "board";
export const PATCH_EVERY_MS = 80;
export const CURSOR_EVERY_MS = 60;
/** Сколько опоздавший ждёт сцену от соседей, прежде чем считать, что открыл доску первым. */
export const HELLO_WAIT_MS = 2_000;
export const SAVE_RETRY_MS = 5_000;
/** Картинка доски уходит в хранилище владельца через 30 с после последней правки и при уходе. */
export const PICTURE_AFTER_MS = 30_000;
export const BOARD_FPS = 10;

const PACKET_VERSION = 1;
const ELEMENTS_CAP = 50_000;
const FILES_CAP = 200;

export type BoardElement = { readonly id: string; readonly version: number };
export type BoardFile = { readonly id: string; readonly dataURL: string; readonly mimeType: string };

export type BoardMessage =
  | { kind: "hello" | "here" | "bye" }
  | { kind: "patch" | "scene"; elements: BoardElement[]; files: BoardFile[] }
  | { kind: "saved"; version: number };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isElement = (value: unknown): value is BoardElement =>
  isRecord(value) && typeof value.id === "string" && value.id !== "" && Number.isFinite(value.version);

// Картинка — только data-URL: ссылка на чужой хост превратила бы доску в канал загрузки чужого содержимого.
const isFile = (value: unknown): value is BoardFile =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.mimeType === "string" &&
  typeof value.dataURL === "string" &&
  value.dataURL.startsWith("data:");

/** Сообщение доски в канал: JSON с версией протокола. */
export const boardPacket = (message: BoardMessage) => JSON.stringify({ v: PACKET_VERSION, ...message });

/** Сообщение доски из канала; null — чужая версия, кривой JSON или неизвестный вид. */
export function boardMessageOf(raw: string): BoardMessage | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(data) || data.v !== PACKET_VERSION) return null;
  switch (data.kind) {
    case "hello":
    case "here":
    case "bye":
      return { kind: data.kind };
    case "saved":
      return Number.isInteger(data.version) ? { kind: "saved", version: Number(data.version) } : null;
    case "patch":
    case "scene": {
      if (!Array.isArray(data.elements) || data.elements.length > ELEMENTS_CAP) return null;
      const files = Array.isArray(data.files) ? data.files.slice(0, FILES_CAP).filter(isFile) : [];
      return { kind: data.kind, elements: data.elements.filter(isElement), files };
    }
    default:
      return null;
  }
}

const encoder = new TextEncoder();
const decoder = new TextDecoder();

/** Пакет курсора: координаты сцены. */
export const cursorPacket = (x: number, y: number) => encoder.encode(JSON.stringify({ v: PACKET_VERSION, x, y }));

/** Курсор из пакета; null — не числа или чужая версия. */
export function cursorOf(payload: Uint8Array): { x: number; y: number } | null {
  try {
    const data: unknown = JSON.parse(decoder.decode(payload));
    if (!isRecord(data) || data.v !== PACKET_VERSION) return null;
    const { x, y } = data;
    return typeof x === "number" && typeof y === "number" && Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
  } catch {
    return null;
  }
}

/**
 * Сохраняет доску и отвечает опоздавшим тот, чья идентичность меньше среди открывших её. Правило считается
 * одинаково у всех, без выборов: один писатель вместо N, спорящих за одну строку.
 */
export function savesAmong(self: string, openers: Iterable<string>): boolean {
  for (const other of openers) if (other < self) return false;
  return true;
}

/** Элементы, которых сосед ещё не видел в этой версии: только они уходят правкой. */
export function changedSince(elements: readonly unknown[], sent: ReadonlyMap<string, number>): BoardElement[] {
  return elements.filter(isElement).filter((element) => sent.get(element.id) !== element.version);
}

/** Сумма версий элементов: растёт с любой правкой — так доска отличает загруженную сцену от изменённой. */
export const versionSum = (elements: readonly unknown[]) =>
  elements.filter(isElement).reduce((sum, element) => sum + element.version, 0);

/** Картинки, ещё не отправленные соседям. */
export function filesSince(files: Readonly<Record<string, unknown>>, sent: ReadonlySet<string>): BoardFile[] {
  return Object.values(files)
    .filter(isFile)
    .filter((file) => !sent.has(file.id));
}
