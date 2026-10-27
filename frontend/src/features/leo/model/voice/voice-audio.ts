import { Downsampler, Framer, fromPcm16, levelOf, OUTPUT_RATE, toPcm16, Upsampler } from "../../domain/voice-pcm";
import captureWorklet from "./capture-worklet?worker&url";
import playbackWorklet from "./playback-worklet?worker&url";

/*
 * Звук голосового режима в браузере (ADR 0070, LV-D8): микрофон с подавлением эха, шума и автоусилением
 * понижается до 16 кГц и уходит кадрами по 40 мс; голос Leo (24 кГц) повышается до частоты устройства и играет
 * из очереди обработчика, которую перебивание сбрасывает сразу. Всё — в потоке звука, основной поток только
 * перекладывает куски.
 */

export interface VoiceAudioEvents {
  /** Кадр микрофона: PCM16 16 кГц, 40 мс. */
  readonly frame: (frame: ArrayBuffer) => void;
  /** Громкость микрофона, 0…1, — для сферы. */
  readonly level: (level: number) => void;
  /** Голос Leo зазвучал или его очередь опустела. */
  readonly speaking: (playing: boolean) => void;
}

export interface VoiceAudio {
  readonly play: (pcm: ArrayBuffer) => void;
  readonly flush: () => void;
  readonly setMuted: (muted: boolean) => void;
  readonly close: () => Promise<void>;
}

const MICROPHONE: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
  channelCount: 1,
};

/** Микрофон и динамик голосового режима; ошибка доступа к микрофону — исключение `getUserMedia`. */
export async function openVoiceAudio(events: VoiceAudioEvents): Promise<VoiceAudio> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: MICROPHONE });
  const context = new AudioContext({ latencyHint: "interactive" });
  try {
    await Promise.all([
      context.audioWorklet.addModule(captureWorklet),
      context.audioWorklet.addModule(playbackWorklet),
    ]);
    await context.resume();
  } catch (error) {
    for (const track of stream.getTracks()) track.stop();
    await context.close();
    throw error;
  }
  const capture = new AudioWorkletNode(context, "leo-voice-capture", { numberOfOutputs: 0 });
  context.createMediaStreamSource(stream).connect(capture);
  const playback = new AudioWorkletNode(context, "leo-voice-playback", {
    numberOfInputs: 0,
    outputChannelCount: [1],
  });
  playback.connect(context.destination);

  const down = new Downsampler(context.sampleRate);
  const framer = new Framer();
  const up = new Upsampler(OUTPUT_RATE, context.sampleRate);
  let muted = false;

  capture.port.onmessage = (event: MessageEvent<Float32Array>) => {
    const samples = down.push(event.data);
    events.level(muted ? 0 : levelOf(samples));
    if (muted) return;
    for (const frame of framer.push(toPcm16(samples))) events.frame(frame);
  };
  playback.port.onmessage = (event: MessageEvent<"playing" | "drained">) => events.speaking(event.data === "playing");

  return {
    play: (pcm) => {
      const samples = up.push(fromPcm16(pcm));
      if (samples.length > 0) playback.port.postMessage(samples, [samples.buffer]);
    },
    flush: () => playback.port.postMessage("flush"),
    setMuted: (value) => {
      muted = value;
      for (const track of stream.getAudioTracks()) track.enabled = !value;
    },
    close: async () => {
      for (const track of stream.getTracks()) track.stop();
      capture.disconnect();
      playback.disconnect();
      await context.close();
    },
  };
}
