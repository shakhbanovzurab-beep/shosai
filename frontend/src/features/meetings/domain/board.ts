/* Доска звонка: сцена Excalidraw с версией и пределами сервера (MR-D13). Домен не знает типов Excalidraw. */

/** Пределы сцены на сервере: элементы, их размер и картинки (413 `scene_too_large`). */
export const BOARD_ELEMENTS_MAX = 20_000;
export const BOARD_ELEMENTS_BYTES_MAX = 4 * 1024 * 1024;
export const BOARD_FILES_BYTES_MAX = 8 * 1024 * 1024;
/** Сохранение ждёт тишины рисования, чтобы не слать сцену на каждый штрих. */
export const BOARD_SAVE_AFTER_MS = 2_500;

export type BoardScene = { elements: readonly unknown[]; files: Readonly<Record<string, unknown>> };

/** `saved` — сцена на сервере; `conflict` — её сохранил другой, нужна свежая; `too_large` — сверх пределов. */
export type BoardSave = "loading" | "saved" | "saving" | "conflict" | "too_large" | "failed";

export type BoardCursor = { identity: string; name: string; x: number; y: number };

const bytesOf = (value: unknown) => new TextEncoder().encode(JSON.stringify(value)).length;

/** Сверх ли сцена пределов сервера: число элементов, их байты, байты картинок. */
export function sceneTooLarge(scene: BoardScene): boolean {
  return (
    scene.elements.length > BOARD_ELEMENTS_MAX ||
    bytesOf(scene.elements) > BOARD_ELEMENTS_BYTES_MAX ||
    bytesOf(scene.files) > BOARD_FILES_BYTES_MAX
  );
}

/** `streams` — этот участник показывает доску видеодорожкой: идёт запись, и доску сохраняет он. */
export type BoardState = { save: BoardSave; readOnly: boolean; cursors: BoardCursor[]; streams: boolean };

/** Доска звонка: загрузка, изменения, курсоры других; чужие правки и свежая сцена приходят через `onRemote`. */
export interface BoardSession {
  subscribe(listener: () => void): () => void;
  state(): BoardState;
  /** Человек открыл доску: сцена, с которой она начинается. */
  load(): Promise<BoardScene>;
  /** Сцена на холсте изменилась — своей правкой или слиянием чужой. */
  change(scene: BoardScene): void;
  /** Взять свежую сцену после конфликта; она приходит через `onRemote`. */
  reload(): Promise<void>;
  pointer(x: number, y: number): void;
  onRemote(listener: (scene: BoardScene) => void): () => void;
  /** Показывать холсты доски видеодорожкой, пока `streams`; функция останавливает показ. */
  stream(container: HTMLElement): () => void;
  /** Человек закрыл доску: остальные его больше не ждут, последняя правка сохраняется. */
  close(): Promise<void>;
  /** Звонок закончился: доска только для чтения. */
  end(): void;
}
