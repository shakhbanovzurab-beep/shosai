import { useEffect, useState, useSyncExternalStore } from "react";

/* Свои камера и микрофон до звонка и в нём: разрешение браузера, выбор устройства, включение дорожек. */

/** `asking` — ждём ответа браузера; `blocked` — человек или браузер запретил; `none` — устройств нет. */
export type MediaAccess = "asking" | "ready" | "blocked" | "none";
export type DeviceChoice = { audio: string | null; video: string | null };

type MediaState = {
  stream: MediaStream | null;
  access: MediaAccess;
  devices: MediaDeviceInfo[];
  choice: DeviceChoice;
  mic: boolean;
  camera: boolean;
};

const stopAll = (stream: MediaStream | null) => {
  for (const track of stream?.getTracks() ?? []) track.stop();
};

const constraintOf = (deviceId: string | null) => (deviceId ? { deviceId: { exact: deviceId } } : true);

/** Устройства страницы вне React: запрос разрешения и смена устройства не меняют состояние из эффектов. */
function createMediaStore() {
  let state: MediaState = {
    stream: null,
    access: "asking",
    devices: [],
    choice: { audio: null, video: null },
    mic: true,
    camera: true,
  };
  let request = 0;
  const listeners = new Set<() => void>();
  const update = (change: Partial<MediaState>) => {
    state = { ...state, ...change };
    for (const listener of listeners) listener();
  };

  async function acquire() {
    const media = navigator.mediaDevices;
    const mine = ++request;
    if (!media?.getUserMedia) return update({ access: "none" });
    update({ access: "asking" });
    try {
      const stream = await media.getUserMedia({
        audio: constraintOf(state.choice.audio),
        video: constraintOf(state.choice.video),
      });
      if (mine !== request) return stopAll(stream);
      for (const track of stream.getAudioTracks()) track.enabled = state.mic;
      for (const track of stream.getVideoTracks()) track.enabled = state.camera;
      stopAll(state.stream);
      update({ stream, access: "ready", devices: await media.enumerateDevices() });
    } catch (error) {
      if (mine !== request) return;
      update({ access: error instanceof DOMException && error.name === "NotAllowedError" ? "blocked" : "none" });
    }
  }

  return {
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    snapshot: () => state,
    start: () => void acquire(),
    stop: () => {
      request += 1;
      stopAll(state.stream);
      update({ stream: null, access: "asking" });
    },
    // Выключенная дорожка остаётся в потоке: включение мгновенно и без нового запроса разрешения.
    setMic: (mic: boolean) => {
      for (const track of state.stream?.getAudioTracks() ?? []) track.enabled = mic;
      update({ mic });
    },
    setCamera: (camera: boolean) => {
      for (const track of state.stream?.getVideoTracks() ?? []) track.enabled = camera;
      update({ camera });
    },
    choose: (kind: keyof DeviceChoice, deviceId: string) => {
      update({ choice: { ...state.choice, [kind]: deviceId } });
      void acquire();
    },
    retry: () => void acquire(),
  };
}

export function useLocalMedia() {
  const [store] = useState(createMediaStore);
  useEffect(() => {
    store.start();
    return store.stop;
  }, [store]);
  const state = useSyncExternalStore(store.subscribe, store.snapshot);
  return {
    ...state,
    setMic: store.setMic,
    setCamera: store.setCamera,
    choose: store.choose,
    retry: store.retry,
    microphones: state.devices.filter((device) => device.kind === "audioinput"),
    cameras: state.devices.filter((device) => device.kind === "videoinput"),
  };
}

export type LocalMedia = ReturnType<typeof useLocalMedia>;
