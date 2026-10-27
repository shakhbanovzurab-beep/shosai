/*
 * Звук голосового режима Leo (ADR 0070, LV-D8): микрофон уходит на сервер PCM16 моно 16 кГц кадрами по 40 мс,
 * голос Leo приходит PCM16 моно 24 кГц. Частота микрофона — частота устройства (44,1 или 48 кГц), поэтому
 * отсчёты понижаются до 16 кГц усреднением окна: оно же гасит частоты выше половины новой.
 */

export const INPUT_RATE = 16_000;
export const OUTPUT_RATE = 24_000;
export const FRAME_MS = 40;
export const FRAME_SAMPLES = (INPUT_RATE * FRAME_MS) / 1000;

/** Понижение частоты потока: куски любой длины, дробная позиция переходит в следующий кусок. */
export class Downsampler {
  private readonly ratio: number;
  private pending: number[] = [];
  private position = 0;

  constructor(fromRate: number, toRate = INPUT_RATE) {
    if (fromRate < toRate) throw new RangeError("частота источника ниже частоты кадров");
    this.ratio = fromRate / toRate;
  }

  /** Отсчёты на новой частоте, которые уже набрались. */
  push(samples: Float32Array): Float32Array {
    for (const sample of samples) this.pending.push(sample);
    const out: number[] = [];
    while (this.position + this.ratio <= this.pending.length) {
      const start = Math.floor(this.position);
      const end = Math.floor(this.position + this.ratio);
      let sum = 0;
      for (let at = start; at < end; at++) sum += this.pending[at];
      out.push(sum / Math.max(1, end - start));
      this.position += this.ratio;
    }
    const consumed = Math.floor(this.position);
    this.pending = this.pending.slice(consumed);
    this.position -= consumed;
    return Float32Array.from(out);
  }
}

/**
 * Повышение частоты голоса Leo до частоты устройства линейной интерполяцией. Позиция выходного отсчёта n —
 * ровно n·from/to входного, в целых числах, поэтому длинный разговор не накапливает ошибку; отсчёт выходит,
 * когда пришёл следующий за ним входной, — последний входной отсчёт куска ждёт следующего куска.
 */
export class Upsampler {
  private readonly from: number;
  private readonly to: number;
  private produced = 0;
  private consumed = 0;
  private previous = 0;

  constructor(fromRate: number, toRate: number) {
    if (toRate < fromRate) throw new RangeError("частота устройства ниже частоты голоса");
    this.from = fromRate;
    this.to = toRate;
  }

  /** Отсчёты на частоте устройства, которые уже можно вычислить. */
  push(samples: Float32Array): Float32Array {
    const available = this.consumed + samples.length;
    const sampleAt = (index: number) => (index < this.consumed ? this.previous : samples[index - this.consumed]);
    const out: number[] = [];
    for (;;) {
      const scaled = this.produced * this.from;
      const index = Math.floor(scaled / this.to);
      if (index + 1 >= available) break;
      const fraction = (scaled - index * this.to) / this.to;
      const left = sampleAt(index);
      out.push(left + (sampleAt(index + 1) - left) * fraction);
      this.produced += 1;
    }
    if (samples.length > 0) this.previous = samples[samples.length - 1];
    this.consumed = available;
    return Float32Array.from(out);
  }
}

/** Отсчёты [-1, 1] в PCM16: за пределами — край шкалы. */
export function toPcm16(samples: Float32Array): Int16Array {
  const out = new Int16Array(samples.length);
  samples.forEach((sample, at) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    out[at] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  });
  return out;
}

/** PCM16 little-endian (как шлёт сервер) в отсчёты [-1, 1] для воспроизведения. */
export function fromPcm16(bytes: ArrayBuffer): Float32Array {
  const view = new DataView(bytes);
  const out = new Float32Array(Math.floor(bytes.byteLength / 2));
  for (let at = 0; at < out.length; at++) out[at] = view.getInt16(at * 2, true) / 0x8000;
  return out;
}

/** Нарезка PCM16 на кадры по 40 мс: остаток ждёт следующих отсчётов. */
export class Framer {
  private pending: number[] = [];

  /** Готовые кадры, каждый — байты PCM16 little-endian. */
  push(samples: Int16Array): ArrayBuffer[] {
    for (const sample of samples) this.pending.push(sample);
    const frames: ArrayBuffer[] = [];
    while (this.pending.length >= FRAME_SAMPLES) {
      const frame = new DataView(new ArrayBuffer(FRAME_SAMPLES * 2));
      for (let at = 0; at < FRAME_SAMPLES; at++) frame.setInt16(at * 2, this.pending[at], true);
      frames.push(frame.buffer);
      this.pending = this.pending.slice(FRAME_SAMPLES);
    }
    return frames;
  }
}

/** Громкость куска, 0…1: среднеквадратичное значение — по нему дышит сфера. */
export function levelOf(samples: Float32Array): number {
  if (samples.length === 0) return 0;
  let sum = 0;
  for (const sample of samples) sum += sample * sample;
  return Math.min(1, Math.sqrt(sum / samples.length));
}
