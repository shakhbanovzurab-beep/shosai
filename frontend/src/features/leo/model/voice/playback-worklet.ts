// Окружение AudioWorklet: его типов нет в библиотеке DOM TypeScript; объявлено то, чем пользуется обработчик.
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
  constructor();
}
declare function registerProcessor(name: string, processor: new () => AudioWorkletProcessor): void;

/*
 * Голос Leo в потоке звука: куски играют по очереди; «flush» сбрасывает очередь сразу — так Leo замолкает,
 * когда человек его перебил. Основной поток узнаёт, когда звук пошёл и когда очередь опустела.
 */
class PlaybackProcessor extends AudioWorkletProcessor {
  private queue: Float32Array[] = [];
  private offset = 0;
  private playing = false;

  constructor() {
    super();
    this.port.onmessage = (event: MessageEvent<Float32Array | "flush">) => {
      if (event.data === "flush") {
        this.queue = [];
        this.offset = 0;
      } else {
        this.queue.push(event.data);
      }
    };
  }

  process(_inputs: Float32Array[][], outputs: Float32Array[][]): boolean {
    const out = outputs[0]?.[0];
    if (!out) return true;
    let at = 0;
    while (at < out.length && this.queue.length > 0) {
      const head = this.queue[0];
      const take = Math.min(out.length - at, head.length - this.offset);
      out.set(head.subarray(this.offset, this.offset + take), at);
      at += take;
      this.offset += take;
      if (this.offset >= head.length) {
        this.queue.shift();
        this.offset = 0;
      }
    }
    out.fill(0, at);
    const playing = at > 0;
    if (playing !== this.playing) {
      this.playing = playing;
      this.port.postMessage(playing ? "playing" : "drained");
    }
    return true;
  }
}

registerProcessor("leo-voice-playback", PlaybackProcessor);

// Модуль, а не скрипт: объявления выше не становятся глобальными для кабинета.
export {};
