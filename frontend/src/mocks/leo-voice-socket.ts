import { ws } from "msw";

import { FRAME_MS, OUTPUT_RATE, toPcm16 } from "@/features/leo/domain/voice-pcm";

/*
 * Голосовой режим в `npm run dev`: сокет `/v1/ws/voice` отвечает моком (ADR 0070). На `hello` — `ready`;
 * после полутора секунд речи — расшифровка, «думаю» и ответ: мягкий аккорд вместо голоса Leo, кусками
 * по 40 мс, как шлёт сервер. Перебить можно: новая речь посреди ответа шлёт `interrupted`.
 */

const SPEECH_FRAMES = Math.round(1500 / FRAME_MS);
const ANSWER_SECONDS = 1.6;
const PERSON = "Что у меня сегодня?";
const LEO = "Сегодня две встречи и одна задача со сроком — начнём с подготовки к планёрке.";

/** Аккорд вместо голоса: тихий, с затуханием, PCM16 24 кГц, кусками по 40 мс. */
function chord(): ArrayBuffer[] {
  const total = Math.round(OUTPUT_RATE * ANSWER_SECONDS);
  const samples = Float32Array.from({ length: total }, (_, at) => {
    const time = at / OUTPUT_RATE;
    const fade = Math.min(1, time * 8) * Math.max(0, 1 - time / ANSWER_SECONDS);
    return 0.12 * fade * (Math.sin(2 * Math.PI * 220 * time) + 0.5 * Math.sin(2 * Math.PI * 330 * time));
  });
  const pcm = toPcm16(samples);
  const step = (OUTPUT_RATE * FRAME_MS) / 1000;
  const chunks: ArrayBuffer[] = [];
  for (let at = 0; at < pcm.length; at += step) chunks.push(pcm.slice(at, at + step).buffer);
  return chunks;
}

const send = (client: { send: (data: string | ArrayBuffer) => void }, frame: object) =>
  client.send(JSON.stringify(frame));

export const voiceSocket = ws.link(/\/v1\/ws\/voice$/).addEventListener("connection", ({ client }) => {
  let heard = 0;
  let answering = false;
  let timers: number[] = [];
  const later = (ms: number, run: () => void) => timers.push(window.setTimeout(run, ms));

  const answer = () => {
    answering = true;
    send(client, { type: "transcript", who: "person", text: PERSON, final: true });
    send(client, { type: "state", state: "thinking" });
    later(700, () => {
      send(client, { type: "state", state: "speaking" });
      send(client, { type: "transcript", who: "leo", text: LEO, final: true });
      for (const [index, chunk] of chord().entries()) later(index * FRAME_MS, () => client.send(chunk));
      later(ANSWER_SECONDS * 1000, () => {
        answering = false;
        send(client, { type: "state", state: "listening" });
      });
    });
  };

  client.addEventListener("message", (event) => {
    if (typeof event.data !== "string") {
      heard += 1;
      if (answering && heard > 10) {
        for (const timer of timers) window.clearTimeout(timer);
        timers = [];
        answering = false;
        heard = 0;
        send(client, { type: "interrupted" });
      } else if (!answering && heard >= SPEECH_FRAMES) {
        heard = 0;
        answer();
      }
      return;
    }
    const frame = JSON.parse(event.data) as { type?: string; thread_id?: string | null };
    if (frame.type === "hello") {
      send(client, {
        type: "ready",
        session: "demo-voice",
        thread_id: frame.thread_id ?? "demo-voice-thread",
        input_rate: 16_000,
        output_rate: OUTPUT_RATE,
      });
      send(client, { type: "state", state: "listening" });
    } else if (frame.type === "end") {
      for (const timer of timers) window.clearTimeout(timer);
      client.close(1000);
    }
  });
});
