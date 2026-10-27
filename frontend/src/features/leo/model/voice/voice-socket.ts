import { accessToken, renewSession } from "@/features/identity/model/session";

import {
  VOICE_PROTOCOL,
  type VoiceEnd,
  type VoiceHello,
  type VoiceScope,
  type VoiceServerFrame,
  voiceEndOf,
  voiceFrameOf,
} from "../../domain/voice-wire";

/*
 * Сокет голосового режима (ADR 0070): `WS /v1/ws/voice` того же origin, что кабинет; первый кадр — `hello`
 * с токеном доступа (в адресе токена нет: адреса попадают в журналы). Остановка шлюза (1012) и полный процесс
 * (1013) — повод подключиться ещё раз; истёкший токен (4401) — обновить его и подключиться; один раз подряд.
 */

export interface VoiceTarget {
  readonly scope: VoiceScope;
  readonly threadId: string | null;
  /** Страница, с которой человек говорит: Leo берёт инструменты страницы, как в чате. */
  readonly path: string;
  readonly locale: string;
}

export interface VoiceSocketEvents {
  readonly frame: (frame: VoiceServerFrame) => void;
  readonly audio: (pcm: ArrayBuffer) => void;
  readonly ended: (end: VoiceEnd) => void;
}

/** Адрес сокета голоса на origin кабинета: wss для https. */
export function voiceUrl(href: string): string {
  const url = new URL("/v1/ws/voice", href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export class VoiceSocket {
  private socket: WebSocket | null = null;
  private retried = false;
  private closing = false;
  /** Тред разговора: из `ready`, если сервер завёл новый. */
  threadId: string | null;

  constructor(
    private readonly target: VoiceTarget,
    private readonly events: VoiceSocketEvents,
  ) {
    this.threadId = target.threadId;
  }

  /** Подключиться; без сессии входа разговор кончается сразу. */
  async open(): Promise<void> {
    const token = accessToken() ?? (await renewSession(null));
    if (token === null) this.events.ended("signedOut");
    else this.connect(token);
  }

  /** Кадр микрофона, если сокет открыт; закрытый сокет звук не копит. */
  send(frame: ArrayBuffer): void {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(frame);
  }

  /** Конец разговора по воле человека. */
  close(): void {
    this.closing = true;
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify({ type: "end" }));
    this.socket?.close(1000);
  }

  private connect(token: string): void {
    const socket = new WebSocket(voiceUrl(window.location.href));
    socket.binaryType = "arraybuffer";
    socket.onopen = () => socket.send(JSON.stringify(this.hello(token)));
    socket.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
      if (typeof event.data !== "string") {
        this.events.audio(event.data);
        return;
      }
      const frame = voiceFrameOf(event.data);
      if (frame === null) return;
      if (frame.type === "ready") {
        // Новый разговор после переподключения продолжает тот же тред.
        this.threadId = frame.thread_id;
        this.retried = false;
      }
      this.events.frame(frame);
    };
    socket.onclose = (event) => void this.closed(event.code, event.reason, token);
    this.socket = socket;
  }

  private hello(token: string): VoiceHello {
    const { scope, path, locale } = this.target;
    return { type: "hello", v: VOICE_PROTOCOL, token, scope, thread_id: this.threadId, path, locale };
  }

  private async closed(code: number, reason: string, token: string): Promise<void> {
    this.socket = null;
    if (this.closing) {
      this.events.ended("ended");
      return;
    }
    const end = voiceEndOf(code, reason);
    if (!this.retried && (end === "reconnect" || end === "signedOut")) {
      this.retried = true;
      const next = end === "signedOut" ? await renewSession(token) : token;
      if (next !== null) {
        this.connect(next);
        return;
      }
    }
    this.events.ended(end);
  }
}
