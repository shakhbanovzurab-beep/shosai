// Окружение AudioWorklet: его типов нет в библиотеке DOM TypeScript; объявлено то, чем пользуется обработчик.
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
  constructor();
}
declare function registerProcessor(name: string, processor: new () => AudioWorkletProcessor): void;
declare const sampleRate: number;

// Микрофон в потоке звука: отсчёты копятся кусками по 20 мс и уходят в основной поток без копирования.
const CHUNK_SECONDS = 0.02;

class CaptureProcessor extends AudioWorkletProcessor {
  // Размер — отдельно: отданный основному потоку буфер отсоединяется, и длина куска становится нулевой.
  private readonly size = Math.round(sampleRate * CHUNK_SECONDS);
  private chunk = new Float32Array(this.size);
  private filled = 0;

  process(inputs: Float32Array[][]): boolean {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    let at = 0;
    while (at < channel.length) {
      const take = Math.min(channel.length - at, this.chunk.length - this.filled);
      this.chunk.set(channel.subarray(at, at + take), this.filled);
      this.filled += take;
      at += take;
      if (this.filled === this.chunk.length) {
        this.port.postMessage(this.chunk, [this.chunk.buffer]);
        this.chunk = new Float32Array(this.size);
        this.filled = 0;
      }
    }
    return true;
  }
}

registerProcessor("leo-voice-capture", CaptureProcessor);

// Модуль, а не скрипт: объявления выше не становятся глобальными для кабинета.
export {};
