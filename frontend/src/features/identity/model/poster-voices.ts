/**
 * Последние реплики, прозвучавшие на афише входа. Их показывает панель над пилюлей; поле сумбура добавляет
 * реплики несколько раз в секунду, поэтому перерисовывается только подписанная панель, а не вся сцена.
 */
export interface HeardLine {
  /** Порядковый номер реплики: одна и та же фраза может прозвучать снова. */
  id: number;
  line: string;
}

export interface PosterVoices {
  heard(line: string): void;
  subscribe(listener: () => void): () => void;
  recent(): readonly HeardLine[];
}

const KEPT = 3;

export function createPosterVoices(): PosterVoices {
  let lines: readonly HeardLine[] = [];
  let count = 0;
  const listeners = new Set<() => void>();
  return {
    heard(line) {
      count += 1;
      lines = [...lines, { id: count, line }].slice(-KEPT);
      for (const listener of listeners) listener();
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    recent: () => lines,
  };
}
