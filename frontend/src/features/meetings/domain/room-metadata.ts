import type { CallMarks } from "./call-session";

/* Метаданные комнаты LiveKit от сервера: id комнаты, принципал владельца и отметки (frontend/docs/meetings-api.md). */

export type RoomMetadata = { roomId: string; owner: string | null; marks: CallMarks };

/** Метаданные версии 1; другие и испорченные — null, их показывать нечего. */
export function roomMetadataOf(text: string | undefined): RoomMetadata | null {
  let body: unknown;
  try {
    body = JSON.parse(text ?? "");
  } catch {
    return null;
  }
  if (typeof body !== "object" || body === null) return null;
  const { v, room_id: roomId, owner, marks } = body as Record<string, unknown>;
  if (v !== 1 || typeof roomId !== "string" || typeof marks !== "object" || marks === null) return null;
  const { notes, recording } = marks as Record<string, unknown>;
  if (typeof notes !== "boolean" || typeof recording !== "boolean") return null;
  return { roomId, owner: typeof owner === "string" ? owner : null, marks: { notes, recording } };
}
