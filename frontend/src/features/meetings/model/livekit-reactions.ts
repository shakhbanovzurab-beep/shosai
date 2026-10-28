import {
  admitReaction,
  REACTION_SHOWN_MS,
  type Reaction,
  type ShownReaction,
  shownReactions,
} from "../domain/reactions";

/* Реакции звонка: свой лимит при отправке и лимит каждого отправителя при приёме, показ на 4 секунды (MR-D12). */

const encoder = new TextEncoder();

export class ReactionDesk {
  private shown: ShownReaction[] = [];
  private sent: number[] = [];
  private readonly received = new Map<string, number[]>();

  constructor(private readonly onChange: (shown: ShownReaction[]) => void) {}

  /** Пакет своей реакции `{v: 1, emoji}`; null — лимит 10 за 10 секунд исчерпан. */
  send(emoji: Reaction, self: string): Uint8Array<ArrayBuffer> | null {
    const now = Date.now();
    const gate = admitReaction(this.sent, now);
    this.sent = gate.times;
    if (!gate.admitted) return null;
    this.show(emoji, self, now);
    return encoder.encode(JSON.stringify({ v: 1, emoji }));
  }

  /** Чужая реакция; сверх лимита отправителя не показывается — поток не забьёт экран. */
  receive(emoji: Reaction, from: string) {
    const now = Date.now();
    const gate = admitReaction(this.received.get(from) ?? [], now);
    this.received.set(from, gate.times);
    if (gate.admitted) this.show(emoji, from, now);
  }

  private show(emoji: Reaction, from: string, at: number) {
    this.shown = shownReactions([...this.shown, { id: `${from}-${at}-${this.shown.length}`, emoji, from, at }], at);
    this.onChange(this.shown);
    setTimeout(() => {
      this.shown = shownReactions(this.shown, Date.now());
      this.onChange(this.shown);
    }, REACTION_SHOWN_MS + 100);
  }
}
