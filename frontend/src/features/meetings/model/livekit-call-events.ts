import {
  type LocalTrackPublication,
  type Participant,
  type RemoteParticipant,
  type RemoteTrack,
  type Room,
  RoomEvent,
  type TrackPublication,
} from "livekit-client";

import type { CallEnd } from "../domain/join";
import { endOf, stopTrack } from "./livekit-media";
import type { TrackStage } from "./livekit-tracks";

/* События комнаты LiveKit, на которые отвечает звонок (meetings A10): люди, дорожки, данные, связь. */

export type CallEvents = {
  refresh: () => void;
  receive: (payload: Uint8Array, participant: RemoteParticipant | undefined, topic: string | undefined) => void;
  reconnecting: () => void;
  reconnected: () => void;
  ended: (end: CallEnd) => void;
};

/** Когда началась встреча — создание комнаты на сервере звонков; null, пока он не ответил на вход. */
export function startedAtOf(room: Room): number | null {
  const info = room.engine?.latestJoinResponse?.room;
  const created = info ? info.creationTimeMs || info.creationTime * 1000n : 0n;
  return created > 0n ? Number(created) : null;
}

/** Подписать звонок на события комнаты: видео сцены — по плиткам, звук — от всех. */
export function listenToRoom(room: Room, stage: TrackStage, events: CallEvents) {
  room
    .on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
      stage.subscribeAudio(participant);
      events.refresh();
    })
    .on(RoomEvent.TrackPublished, (publication, participant) => stage.want(publication, participant))
    .on(RoomEvent.TrackSubscribed, (track: RemoteTrack, _publication: TrackPublication, participant: Participant) => {
      stage.show(track, participant.identity);
      events.refresh();
    })
    .on(RoomEvent.TrackUnsubscribed, stopTrack)
    .on(RoomEvent.LocalTrackPublished, (publication: LocalTrackPublication) => {
      stage.showLocal(publication);
      events.refresh();
    })
    .on(RoomEvent.DataReceived, (payload, participant, _kind, topic) => events.receive(payload, participant, topic))
    .on(RoomEvent.RoomMetadataChanged, events.refresh)
    .on(RoomEvent.Reconnecting, events.reconnecting)
    .on(RoomEvent.Reconnected, events.reconnected)
    .on(RoomEvent.Disconnected, (reason) => events.ended(endOf(reason)));
  for (const event of [
    RoomEvent.ParticipantDisconnected,
    RoomEvent.TrackMuted,
    RoomEvent.TrackUnmuted,
    RoomEvent.TrackUnpublished,
    RoomEvent.ActiveSpeakersChanged,
    RoomEvent.ParticipantAttributesChanged,
    RoomEvent.ParticipantNameChanged,
  ])
    room.on(event, events.refresh);
}
