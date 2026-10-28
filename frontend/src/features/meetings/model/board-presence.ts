import type { BoardCursor } from "../domain/board";
import { HELLO_WAIT_MS, savesAmong } from "../domain/board-protocol";

/*
 * Кто ещё открыл доску и где его курсор. Сохраняет тот, чья идентичность меньше среди открывших; только что
 * открывший сначала 2 с слушает соседей — до их ответа он не знает, что не один, и не должен сохранять.
 */

export class BoardPresence {
  private readonly openers = new Set<string>();
  private readonly pointers = new Map<string, BoardCursor>();
  private openedAt = Number.POSITIVE_INFINITY;

  constructor(
    private readonly self: () => string,
    private readonly nameOf: (identity: string) => string,
  ) {}

  open() {
    this.openedAt = Date.now();
  }

  close() {
    this.openedAt = Number.POSITIVE_INFINITY;
    this.openers.clear();
    this.pointers.clear();
  }

  joined(identity: string) {
    this.openers.add(identity);
  }

  /** Сосед закрыл доску или ушёл; true — его курсор пропал. */
  left(identity: string): boolean {
    this.openers.delete(identity);
    return this.pointers.delete(identity);
  }

  point(identity: string, x: number, y: number) {
    this.pointers.set(identity, { identity, name: this.nameOf(identity), x, y });
  }

  cursors = () => [...this.pointers.values()];

  /** Сохраняет ли доску этот участник. */
  saves(): boolean {
    return Date.now() - this.openedAt >= HELLO_WAIT_MS && savesAmong(this.self(), this.openers);
  }
}
