import type { BoardScene } from "../domain/board";
import {
  type BoardElement,
  type BoardFile,
  type BoardMessage,
  changedSince,
  filesSince,
  PATCH_EVERY_MS,
} from "../domain/board-protocol";

/*
 * Правки доски соседям: не чаще раза в 80 мс и только элементы версий, которых соседи ещё не видели. Пришедшее
 * от соседей считается увиденным — эхом обратно оно не уходит.
 */

/** Вся сцена в виде сообщения: её получает опоздавший от того, кто сохраняет. */
export const wholeScene = (scene: BoardScene) => ({
  elements: changedSince(scene.elements, new Map()),
  files: filesSince(scene.files, new Set()),
});

export class BoardPatches {
  private readonly sent = new Map<string, number>();
  private readonly sentFiles = new Set<string>();
  private timer: number | undefined;
  private sentAt = 0;

  constructor(
    private readonly latest: () => BoardScene,
    private readonly send: (message: BoardMessage) => void,
  ) {}

  /** Сцена изменилась: правка уйдёт, как только позволит частота. */
  queue() {
    if (this.timer !== undefined) return;
    const wait = Math.max(0, PATCH_EVERY_MS - (Date.now() - this.sentAt));
    this.timer = window.setTimeout(() => this.flush(), wait);
  }

  /** Отправить ждущую правку сразу — перед уходом с доски. */
  flush() {
    window.clearTimeout(this.timer);
    this.timer = undefined;
    const scene = this.latest();
    const elements = changedSince(scene.elements, this.sent);
    const files = filesSince(scene.files, this.sentFiles);
    if (elements.length === 0 && files.length === 0) return;
    this.sentAt = Date.now();
    this.send({ kind: "patch", elements, files });
    this.seen(elements, files);
  }

  /** Сцена с сервера: у соседей она уже есть, повторно она не рассылается. */
  seenScene(scene: BoardScene) {
    const whole = wholeScene(scene);
    this.seen(whole.elements, whole.files);
  }

  /** Элементы и картинки, которые соседи уже видели. */
  seen(elements: readonly BoardElement[], files: readonly BoardFile[]) {
    for (const element of elements) this.sent.set(element.id, element.version);
    for (const file of files) this.sentFiles.add(file.id);
  }

  stop() {
    window.clearTimeout(this.timer);
    this.timer = undefined;
  }
}
