import { DisconnectReason, type LocalParticipant, type RemoteTrack, Track } from "livekit-client";

import type { CallSetup } from "../domain/call-session";
import { type ChatMessage, chatOfPacket } from "../domain/chat-log";
import type { CallEnd } from "../domain/join";
import { type Reaction, reactionOfPacket } from "../domain/reactions";

/* Медиа звонка на LiveKit: свои дорожки из лобби, звук остальных, пакеты канала данных. */

const decoder = new TextDecoder();

/** Опубликовать дорожки лобби вместе; выключенные публикуются заглушенными — включение мгновенно. */
export async function publishLobbyTracks(local: LocalParticipant, media: CallSetup["media"]) {
  const publish = async (track: MediaStreamTrack, source: Track.Source, on: boolean) => {
    const publication = await local.publishTrack(track, { source });
    if (!on) await publication.mute();
  };
  await Promise.all([
    ...(media.stream?.getAudioTracks() ?? []).map((track) => publish(track, Track.Source.Microphone, media.mic)),
    ...(media.stream?.getVideoTracks() ?? []).map((track) => publish(track, Track.Source.Camera, media.camera)),
  ]);
}

/** Звук участника — скрытым элементом страницы, пока на него есть подписка. */
export function playAudio(track: RemoteTrack) {
  const element = track.attach();
  element.hidden = true;
  document.body.append(element);
}

export function stopTrack(track: RemoteTrack) {
  for (const element of track.detach()) if (element instanceof HTMLAudioElement) element.remove();
}

function packetOf(payload: Uint8Array): unknown {
  try {
    return JSON.parse(decoder.decode(payload));
  } catch {
    return null;
  }
}

/** Пакет канала данных: чат шлёт только сервер (от участника это подделка), реакцию — участник. */
export function incoming(payload: Uint8Array, from: string | undefined, topic: string | undefined) {
  const packet = packetOf(payload);
  const chat: ChatMessage | null = topic === "chat" && from === undefined ? chatOfPacket(packet) : null;
  const emoji: Reaction | null = topic === "reaction" && from ? reactionOfPacket(packet) : null;
  return { chat, reaction: emoji && from ? { emoji, from } : null };
}

const ENDS: Partial<Record<DisconnectReason, CallEnd>> = {
  [DisconnectReason.CLIENT_INITIATED]: "left",
  [DisconnectReason.ROOM_DELETED]: "ended",
  [DisconnectReason.PARTICIPANT_REMOVED]: "removed",
};

/** Почему звонок закончился у этого участника по причине отключения LiveKit. */
export const endOf = (reason: DisconnectReason | undefined): CallEnd => (reason && ENDS[reason]) || "lost";
