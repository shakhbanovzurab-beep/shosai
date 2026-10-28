import type { ExcalidrawElement } from "@excalidraw/excalidraw/element/types";
import type { BinaryFiles } from "@excalidraw/excalidraw/types";

import { ApiError } from "@/lib/api/errors";

import type { BoardScene } from "../domain/board";
import { PICTURE_AFTER_MS } from "../domain/board-protocol";
import { withBoardAssets } from "./board-editor";

/*
 * Картинка доски для заметок встречи: PNG на белом фоне, не больше 4096 px по стороне. Excalidraw грузится
 * динамически — тем же чанком, что холст, — поэтому страница комнаты без доски его не тянет.
 */

const SIDE_MAX = 4_096;
const BYTES_MAX = 25 * 1024 * 1024;

/** PNG видимой части сцены; null — рисовать нечего или картинка сверх предела сервера. */
export async function boardPicture(scene: BoardScene): Promise<Blob | null> {
  const elements = (scene.elements as readonly ExcalidrawElement[]).filter((element) => !element.isDeleted);
  if (elements.length === 0) return null;
  const { exportToBlob } = await withBoardAssets(() => import("@excalidraw/excalidraw"));
  const picture = await exportToBlob({
    elements,
    files: scene.files as BinaryFiles,
    mimeType: "image/png",
    maxWidthOrHeight: SIDE_MAX,
    appState: { exportBackground: true, viewBackgroundColor: "#ffffff" },
  });
  return picture.size <= BYTES_MAX ? picture : null;
}

/**
 * Сделать и положить картинку: `refused` — у владельца нет места, и картинок этого звонка больше не будет;
 * `failed` — сбой, следующая попытка со следующей правкой или при уходе.
 */
export async function storePicture(
  scene: BoardScene,
  upload: (picture: Blob) => Promise<void>,
): Promise<"stored" | "empty" | "refused" | "failed"> {
  const picture = await boardPicture(scene).catch(() => null);
  if (!picture) return "empty";
  try {
    await upload(picture);
    return "stored";
  } catch (error) {
    return error instanceof ApiError && error.code === "storage_limit" ? "refused" : "failed";
  }
}

/** Картинка доски в хранилище владельца: через 30 с тишины после правки и сразу — при уходе с доски. */
export class BoardPictures {
  // Правок с последней картинки: картинка не перекладывается, если доска не менялась.
  private unpictured = 0;
  private outcome: "wanted" | "refused" = "wanted";
  private timer: number | undefined;

  constructor(
    private readonly scene: () => BoardScene,
    private readonly upload: (picture: Blob) => Promise<void>,
  ) {}

  touch() {
    this.unpictured += 1;
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => void this.flush(), PICTURE_AFTER_MS);
  }

  async flush() {
    window.clearTimeout(this.timer);
    if (this.unpictured === 0 || this.outcome === "refused") return;
    this.unpictured = 0;
    const outcome = await storePicture(this.scene(), this.upload);
    if (outcome === "refused") this.outcome = "refused";
    if (outcome === "failed") this.unpictured += 1;
  }

  stop() {
    window.clearTimeout(this.timer);
  }
}
