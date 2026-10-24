/*
 * Server-Sent Events, как их пишет поток хода Leo (ADR 0032): строки `event:`, `id:`, `data:`, пустая строка
 * завершает событие, строка с `:` — комментарий-пульс. Разбор идёт по кускам, как они приходят из сети: начало
 * события в одном куске и конец в другом собираются вместе.
 */

export interface SseEvent {
  readonly event: string;
  readonly id: string | null;
  readonly data: string;
}

/** Разбирает поток кусок за куском; отдаёт события, которые уже завершились. */
export class SseParser {
  private buffer = "";
  private event = "message";
  private id: string | null = null;
  private data: string[] = [];

  push(chunk: string): SseEvent[] {
    const text = this.buffer + chunk;
    // `\r` в конце куска может оказаться началом `\r\n`: он ждёт следующего куска.
    const carry = text.endsWith("\r") ? "\r" : "";
    const lines = (carry ? text.slice(0, -1) : text).split(/\r\n|\r|\n/);
    this.buffer = (lines.pop() ?? "") + carry;
    const done: SseEvent[] = [];
    for (const line of lines) {
      const finished = this.line(line);
      if (finished) done.push(finished);
    }
    return done;
  }

  private line(line: string): SseEvent | null {
    if (line === "") return this.dispatch();
    if (line.startsWith(":")) return null;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const raw = colon === -1 ? "" : line.slice(colon + 1);
    const value = raw.startsWith(" ") ? raw.slice(1) : raw;
    if (field === "event") this.event = value;
    else if (field === "id") this.id = value;
    else if (field === "data") this.data.push(value);
    return null;
  }

  private dispatch(): SseEvent | null {
    const ready = this.data.length > 0 ? { event: this.event, id: this.id, data: this.data.join("\n") } : null;
    this.event = "message";
    this.data = [];
    // Номер последнего события остаётся до следующего `id:` — так его и запоминает EventSource.
    return ready;
  }
}
