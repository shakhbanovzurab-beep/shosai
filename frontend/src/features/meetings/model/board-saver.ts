import { ApiError } from "@/lib/api/errors";

import { BOARD_SAVE_AFTER_MS, type BoardSave, type BoardScene } from "../domain/board";
import { SAVE_RETRY_MS } from "../domain/board-protocol";

/*
 * Сохранение доски тем, кто её сохраняет (MR-D13): после паузы рисования сцена уходит с версией, на которой
 * сделана. Чужая версия (409 `scene_stale`) — доска берёт свежую, сливает со своей и сохраняет снова; второй
 * конфликт подряд ждёт человека. Сбой сети повторяется через 5 с; закончившийся звонок не сохраняется.
 */

export type SaverPort = {
  save(scene: BoardScene, version: number): Promise<number>;
  report(save: BoardSave): void;
  /** Сохранено: соседям — новая версия, чтобы следующий сохраняющий начал с неё. */
  saved(version: number): void;
  /** Взять свежую сцену с сервера и слить её с доской; её версия приходит через `adopt`. */
  stale(): Promise<void>;
};

export class BoardSaver {
  private version = 0;
  private pending: BoardScene | null = null;
  private timer: number | undefined;
  private conflicts = 0;
  private busy = false;

  constructor(private readonly port: SaverPort) {}

  /** Версия, которую доска знает: своя, соседа или сервера; меньшая уже устарела. */
  adopt(version: number) {
    this.version = Math.max(this.version, version);
  }

  schedule(scene: BoardScene) {
    this.pending = scene;
    this.port.report("saving");
    this.wait(BOARD_SAVE_AFTER_MS);
  }

  /** Сохранить сразу то, что ждёт, — при уходе или закрытии доски. */
  async flush() {
    window.clearTimeout(this.timer);
    const scene = this.pending;
    if (!scene || this.busy) return;
    this.pending = null;
    this.busy = true;
    try {
      this.version = await this.port.save(scene, this.version);
      this.conflicts = 0;
      this.port.saved(this.version);
      this.port.report(this.pending ? "saving" : "saved");
    } catch (error) {
      await this.refused(scene, error);
    } finally {
      this.busy = false;
    }
    if (this.pending) this.wait(BOARD_SAVE_AFTER_MS);
  }

  /** Человек взял свежую доску после конфликта: сохранение начинается заново. */
  async resume() {
    this.conflicts = 0;
    await this.port.stale();
  }

  stop() {
    window.clearTimeout(this.timer);
    this.pending = null;
  }

  private async refused(scene: BoardScene, error: unknown) {
    const code = error instanceof ApiError ? error.code : null;
    if (code === "scene_too_large") return this.port.report("too_large");
    if (code === "no_live_call") return this.port.report("failed");
    if (code === "scene_stale") {
      this.conflicts += 1;
      if (this.conflicts > 1) return this.port.report("conflict");
      return this.port.stale();
    }
    this.pending ??= scene;
    this.port.report("failed");
    this.wait(SAVE_RETRY_MS);
  }

  private wait(ms: number) {
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => void this.flush(), ms);
  }
}
