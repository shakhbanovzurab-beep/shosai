/* Доска звонка: сцена Excalidraw с версией и пределами сервера (MR-D13). Домен не знает типов Excalidraw. */

/** Пределы сцены на сервере: элементы, их размер и картинки (413 `scene_too_large`). */
export const BOARD_ELEMENTS_MAX = 20_000;
export const BOARD_ELEMENTS_BYTES_MAX = 4 * 1024 * 1024;
export const BOARD_FILES_BYTES_MAX = 8 * 1024 * 1024;
/** Сохранение ждёт тишины рисования, чтобы не слать сцену на каждый штрих. */
export const BOARD_SAVE_AFTER_MS = 1_500;

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

export type BoardState = { save: BoardSave; readOnly: boolean; cursors: BoardCursor[] };

/** Доска звонка: загрузка, изменения, курсоры других; чужие правки приходят через `onRemote`. */
export interface BoardSession {
  subscribe(listener: () => void): () => void;
  state(): BoardState;
  load(): Promise<BoardScene>;
  /** Своя правка: сцена сохраняется после паузы рисования. */
  change(scene: BoardScene): void;
  /** Взять свежую сцену после конфликта. */
  reload(): Promise<BoardScene>;
  pointer(x: number, y: number): void;
  onRemote(listener: (scene: BoardScene) => void): () => void;
  close(): void;
}
