/*
 * Провод голосового режима Leo (ADR 0070, LV-D2): управление — JSON-кадрами, звук — двоичными.
 * Клиент первым кадром шлёт `hello` с версией, токеном и пространством; сервер отвечает `ready` и дальше
 * сообщает состояние разговора, расшифровки обеих сторон, шаги и карточки. Кадр, которого кабинет не знает,
 * пропускается: сервер может прислать новый раньше кабинета.
 */

import type { LeoContext } from "./context";

export const VOICE_PROTOCOL = 1;

export type VoiceScope = { kind: "personal" } | { kind: "workspace"; workspace_id: string };

/** Пространство голосового разговора: человека или workspace; у хаба и платформы голоса нет — null. */
export function voiceScopeOf(context: LeoContext): VoiceScope | null {
  if (context.kind === "personal") return { kind: "personal" };
  return context.kind === "workspace" ? { kind: "workspace", workspace_id: context.id } : null;
}

export type VoiceHello = {
  type: "hello";
  v: typeof VOICE_PROTOCOL;
  token: string;
  scope: VoiceScope;
  thread_id: string | null;
  path: string;
  /** Язык интерфейса: Leo отвечает на нём, пока в настройках Leo язык не задан. */
  locale: string;
};

export type VoiceState = "listening" | "thinking" | "speaking";

export type VoiceServerFrame =
  | { type: "ready"; session: string; thread_id: string; input_rate: number; output_rate: number }
  | { type: "state"; state: VoiceState }
  | { type: "transcript"; who: "person" | "leo"; text: string; final: boolean }
  | { type: "interrupted" }
  | { type: "step"; activity: string; status: "running" | "done" | "failed" }
  | { type: "action.proposed"; action_id: string }
  | { type: "ended"; code: string }
  | { type: "server.shutdown" };

const KINDS = new Set<VoiceServerFrame["type"]>([
  "ready",
  "state",
  "transcript",
  "interrupted",
  "step",
  "action.proposed",
  "ended",
  "server.shutdown",
]);

/** Кадр сервера из текста, или null для незнакомого вида и испорченных данных. */
export function voiceFrameOf(text: string): VoiceServerFrame | null {
  try {
    const frame: unknown = JSON.parse(text);
    if (typeof frame !== "object" || frame === null || !("type" in frame)) return null;
    const kind = (frame as { type: unknown }).type;
    return typeof kind === "string" && KINDS.has(kind as VoiceServerFrame["type"]) ? (frame as VoiceServerFrame) : null;
  } catch {
    return null;
  }
}

/** Коды закрытия сокета: RFC 6455 и свои, `4000 + HTTP-статус` (core/web/sockets.py). */
export const VOICE_CLOSE = {
  normal: 1000,
  restart: 1012,
  tryLater: 1013,
  unauthorized: 4401,
  minutesUsedUp: 4402,
  forbidden: 4403,
  conflict: 4409,
  limited: 4429,
} as const;

export type VoiceEnd = "ended" | "reconnect" | "signedOut" | "minutes" | "tokens" | "busy" | "limit" | "failed";

/** Почему разговор закончился, по коду и причине закрытия (коду ошибки сервера): код для слов кабинета. */
export function voiceEndOf(code: number, reason = ""): VoiceEnd {
  // 4402 — и минуты месяца, и токены Leo: различает причина.
  if (reason === "token_limit") return "tokens";
  switch (code) {
    case VOICE_CLOSE.normal:
      return "ended";
    case VOICE_CLOSE.restart:
    case VOICE_CLOSE.tryLater:
      return "reconnect";
    case VOICE_CLOSE.unauthorized:
      return "signedOut";
    case VOICE_CLOSE.minutesUsedUp:
      return "minutes";
    case VOICE_CLOSE.conflict:
      return "busy";
    case VOICE_CLOSE.limited:
      return "limit";
    default:
      return "failed";
  }
}
