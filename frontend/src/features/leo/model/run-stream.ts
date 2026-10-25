import { type NumberedEvent, runEventOf } from "../domain/run-events";
import { SseParser } from "../domain/sse";

/**
 * События потока прогона по порядку. `handle` говорит, дочитан ли поток: тогда чтение кончается, а остаток потока
 * отменяется. false — поток кончился раньше: оборвался или сервер закрыл его на паузе.
 */
export async function readRun(
  stream: ReadableStream<Uint8Array>,
  handle: (event: NumberedEvent) => boolean,
): Promise<boolean> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  for (let chunk = await reader.read(); !chunk.done; chunk = await reader.read()) {
    for (const sse of parser.push(decoder.decode(chunk.value, { stream: true }))) {
      const event = runEventOf(sse);
      if (event === null || !handle(event)) continue;
      reader.cancel().catch(() => undefined);
      return true;
    }
  }
  return false;
}
