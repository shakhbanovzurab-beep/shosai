import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { VoiceServerFrame } from "../../domain/voice-wire";
import { VoiceSocket, voiceUrl } from "./voice-socket";

const session = vi.hoisted(() => ({ token: "token-1" as string | null, renewed: "token-2" as string | null }));
vi.mock("@/features/identity/model/session", () => ({
  accessToken: () => session.token,
  renewSession: vi.fn(async () => session.renewed),
}));

/** Сокет-двойник: что клиент отправил, и события, которые тест посылает сам. */
class FakeSocket {
  static readonly OPEN = 1;
  static opened: FakeSocket[] = [];
  readyState = 0;
  binaryType = "blob";
  sent: (string | ArrayBuffer)[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string | ArrayBuffer }) => void) | null = null;
  onclose: ((event: { code: number; reason: string }) => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.opened.push(this);
  }

  send(data: string | ArrayBuffer) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
  }

  open() {
    this.readyState = FakeSocket.OPEN;
    this.onopen?.();
  }

  hear(data: string | ArrayBuffer) {
    this.onmessage?.({ data });
  }

  drop(code: number, reason = "") {
    this.readyState = 3;
    this.onclose?.({ code, reason });
  }
}

const target = { scope: { kind: "personal" as const }, threadId: null, path: "/app/productivity", locale: "de" };

function connected() {
  const frames: VoiceServerFrame[] = [];
  const audio: ArrayBuffer[] = [];
  const ended: string[] = [];
  const socket = new VoiceSocket(target, {
    frame: (frame) => frames.push(frame),
    audio: (pcm) => audio.push(pcm),
    ended: (end) => ended.push(end),
  });
  return { socket, frames, audio, ended };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("the voice socket", () => {
  beforeEach(() => {
    FakeSocket.opened = [];
    session.token = "token-1";
    session.renewed = "token-2";
    vi.stubGlobal("WebSocket", FakeSocket);
    vi.stubGlobal("window", { location: { href: "https://shosai.example/app/productivity" } });
  });

  afterEach(() => vi.unstubAllGlobals());

  it("opens on the cabinet's origin with wss and says hello first", async () => {
    const { socket, frames, audio } = connected();
    await socket.open();
    const [wire] = FakeSocket.opened;
    wire.open();
    wire.hear('{"type":"ready","session":"s","thread_id":"t-1","input_rate":16000,"output_rate":24000}');
    wire.hear(new ArrayBuffer(4));

    expect(wire.url).toBe("wss://shosai.example/v1/ws/voice");
    expect(wire.binaryType).toBe("arraybuffer");
    expect(JSON.parse(wire.sent[0] as string)).toEqual({
      type: "hello",
      v: 1,
      token: "token-1",
      scope: { kind: "personal" },
      thread_id: null,
      path: "/app/productivity",
      locale: "de",
    });
    expect(frames.map((frame) => frame.type)).toEqual(["ready"]);
    expect(audio).toHaveLength(1);
    expect(socket.threadId).toBe("t-1");
    expect(voiceUrl("http://localhost:3000/app")).toBe("ws://localhost:3000/v1/ws/voice");
  });

  it("connects once more when the gateway restarts, in the same thread", async () => {
    const { socket, ended } = connected();
    await socket.open();
    FakeSocket.opened[0].open();
    FakeSocket.opened[0].hear('{"type":"ready","session":"s","thread_id":"t-1","input_rate":1,"output_rate":1}');
    FakeSocket.opened[0].drop(1012);
    await flush();
    FakeSocket.opened[1].open();
    FakeSocket.opened[1].drop(1013);
    await flush();

    expect(JSON.parse(FakeSocket.opened[1].sent[0] as string).thread_id).toBe("t-1");
    expect(FakeSocket.opened).toHaveLength(2);
    expect(ended).toEqual(["reconnect"]);
  });

  it("renews an expired token and says hello with the new one", async () => {
    const { socket, ended } = connected();
    await socket.open();
    FakeSocket.opened[0].drop(4401);
    await flush();
    FakeSocket.opened[1].open();

    expect(JSON.parse(FakeSocket.opened[1].sent[0] as string).token).toBe("token-2");
    expect(ended).toEqual([]);
  });

  it("tells spent tokens from used-up minutes by the close reason", async () => {
    const { socket, ended } = connected();
    await socket.open();
    FakeSocket.opened[0].drop(4402, "token_limit");
    await flush();

    expect(ended).toEqual(["tokens"]);
  });

  it("ends at the person's word, and at once without a session", async () => {
    const { socket, ended } = connected();
    await socket.open();
    FakeSocket.opened[0].open();
    socket.close();
    FakeSocket.opened[0].drop(1000);
    expect(JSON.parse(FakeSocket.opened[0].sent.at(-1) as string)).toEqual({ type: "end" });
    expect(ended).toEqual(["ended"]);

    session.token = null;
    session.renewed = null;
    const lonely = connected();
    await lonely.socket.open();
    expect(lonely.ended).toEqual(["signedOut"]);
  });
});
