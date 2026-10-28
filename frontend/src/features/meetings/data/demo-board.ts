import {
  BOARD_SAVE_AFTER_MS,
  type BoardScene,
  type BoardSession,
  type BoardState,
  sceneTooLarge,
} from "../domain/board";
import type { CallPerson } from "../domain/call";

/*
 * Доска на моках: сохраняет сцену в памяти после паузы рисования, двое участников водят курсорами. Ссылка
 * `conflict` показывает, как другой сохранил доску раньше; `readonly` — доску закончившегося звонка (только чтение).
 */

const EMPTY: BoardScene = { elements: [], files: {} };

export class DemoBoard implements BoardSession {
  private current: BoardState;
  private scene: BoardScene = EMPTY;
  private readonly listeners = new Set<() => void>();
  private readonly timers: number[] = [];
  private saving: number | undefined;
  private saves = 0;

  constructor(
    private readonly token: string,
    people: () => CallPerson[],
  ) {
    this.current = { save: "loading", readOnly: token === "readonly", cursors: [] };
    let step = 0;
    this.timers.push(
      window.setInterval(() => {
        step += 1;
        const others = people()
          .filter((person) => !person.isLocal)
          .slice(0, 2);
        const cursors = others.map((person, index) => ({
          identity: person.identity,
          name: person.name,
          x: 200 + index * 260 + Math.cos(step / 12 + index) * 120,
          y: 180 + Math.sin(step / 9 + index) * 90,
        }));
        this.update({ cursors });
      }, 120),
    );
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  state = () => this.current;

  async load() {
    this.update({ save: "saved" });
    return this.scene;
  }

  change(scene: BoardScene) {
    if (this.current.readOnly || this.current.save === "conflict") return;
    window.clearTimeout(this.saving);
    if (sceneTooLarge(scene)) return this.update({ save: "too_large" });
    this.update({ save: "saving" });
    this.saving = window.setTimeout(() => {
      this.saves += 1;
      // На ссылке `conflict` второе сохранение встречает чужую версию: так выглядит 409 `scene_stale`.
      if (this.token === "conflict" && this.saves === 2) return this.update({ save: "conflict" });
      this.scene = scene;
      this.update({ save: "saved" });
    }, BOARD_SAVE_AFTER_MS);
  }

  async reload() {
    this.update({ save: "saved" });
    return this.scene;
  }

  // На моках свой курсор никуда не уходит и чужих правок не приходит: доска одна на вкладку.
  pointer = () => undefined;

  onRemote = () => () => undefined;

  close() {
    for (const timer of this.timers) window.clearInterval(timer);
    window.clearTimeout(this.saving);
  }

  private update(change: Partial<BoardState>) {
    this.current = { ...this.current, ...change };
    for (const listener of this.listeners) listener();
  }
}
