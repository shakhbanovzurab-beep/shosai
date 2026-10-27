import { describe, expect, it } from "vitest";

import { Downsampler, FRAME_SAMPLES, Framer, fromPcm16, levelOf, toPcm16, Upsampler } from "./voice-pcm";

describe("voice audio", () => {
  it("brings 48 kHz to 16 kHz by averaging each window of three", () => {
    const down = new Downsampler(48_000);
    expect(Array.from(down.push(Float32Array.from([0.3, 0.3, 0.3, 0.6, 0.6, 0.6, 0.9])))).toEqual([
      expect.closeTo(0.3, 5),
      expect.closeTo(0.6, 5),
    ]);
    expect(Array.from(down.push(Float32Array.from([0.9, 0.9])))).toEqual([expect.closeTo(0.9, 5)]);
  });

  it("keeps the fractional position across chunks of a 44.1 kHz stream", () => {
    const whole = new Downsampler(44_100).push(new Float32Array(44_100).fill(0.5));
    const chunked = new Downsampler(44_100);
    let count = 0;
    for (let at = 0; at < 44_100; at += 128)
      count += chunked.push(new Float32Array(Math.min(128, 44_100 - at)).fill(0.5)).length;
    expect(whole.length).toBe(16_000);
    expect(count).toBe(16_000);
  });

  it("brings Leo's 24 kHz to the device's 48 kHz, chunk after chunk, with no seam", () => {
    const up = new Upsampler(24_000, 48_000);
    const first = Array.from(up.push(Float32Array.from([0.2, 0.4])));
    const second = Array.from(up.push(Float32Array.from([0.6])));
    expect([...first, ...second].map((value) => Number(value.toFixed(3)))).toEqual([0.2, 0.3, 0.4, 0.5]);
  });

  it("gives the same samples for a whole stream and for its chunks, without drift", () => {
    const stream = Float32Array.from({ length: 24_000 }, (_, at) => Math.sin(at / 7));
    const whole = new Upsampler(24_000, 44_100).push(stream);
    const chunked = new Upsampler(24_000, 44_100);
    const pieces: number[] = [];
    for (let at = 0; at < stream.length; at += 480) pieces.push(...chunked.push(stream.subarray(at, at + 480)));
    expect(pieces).toHaveLength(whole.length);
    expect(Math.max(...pieces.map((value, at) => Math.abs(value - whole[at])))).toBeLessThan(1e-6);
    expect(whole.length).toBeGreaterThanOrEqual(44_098);
    expect(() => new Upsampler(24_000, 16_000)).toThrow(RangeError);
  });

  it("refuses a source slower than the frames", () => {
    expect(() => new Downsampler(8_000)).toThrow(RangeError);
  });

  it("turns samples into PCM16 and back, clamping what is out of range", () => {
    const pcm = toPcm16(Float32Array.from([0, 0.5, -0.5, 1, -1, 2, -2]));
    expect(Array.from(pcm)).toEqual([0, 16383, -16384, 32767, -32768, 32767, -32768]);
    const back = fromPcm16(new Int16Array([0, 16384, -32768]).buffer);
    expect(Array.from(back)).toEqual([0, 0.5, -1]);
  });

  it("cuts 40 ms frames and keeps the rest for the next samples", () => {
    const framer = new Framer();
    expect(framer.push(new Int16Array(FRAME_SAMPLES - 1))).toEqual([]);
    const frames = framer.push(new Int16Array(3).fill(7));
    expect(frames).toHaveLength(1);
    expect(frames[0].byteLength).toBe(FRAME_SAMPLES * 2);
    expect(new DataView(frames[0]).getInt16((FRAME_SAMPLES - 1) * 2, true)).toBe(7);
    expect(framer.push(new Int16Array(FRAME_SAMPLES - 3))).toEqual([]);
    expect(framer.push(new Int16Array(1))).toHaveLength(1);
  });

  it("measures the level of a chunk", () => {
    expect(levelOf(new Float32Array(0))).toBe(0);
    expect(levelOf(new Float32Array(10).fill(0.5))).toBeCloseTo(0.5);
  });
});
