import { type Participant, Track, type TrackPublication } from "livekit-client";

import { BOARD_TRACK } from "../domain/board-protocol";
import { type CallPerson, peopleOf, principalOf } from "../domain/call";
import type { VideoKind } from "../domain/call-session";

/* Участники LiveKit как люди звонка: дорожки, речь, рука из атрибутов, владелец по метаданным комнаты. */

export const SOURCE_OF: Record<VideoKind, Track.Source> = {
  camera: Track.Source.Camera,
  screen: Track.Source.ScreenShare,
};

/** Дорожка участника по источнику; доска во время записи — не его экран: у людей звонка есть сама доска. */
export function publicationOf(participant: Participant, source: Track.Source): TrackPublication | undefined {
  for (const publication of participant.trackPublications.values())
    if (publication.source === source && publication.trackName !== BOARD_TRACK) return publication;
  return undefined;
}

const live = (participant: Participant, source: Track.Source) => {
  const publication = publicationOf(participant, source);
  return publication !== undefined && !publication.isMuted;
};

/** Человек звонка из участника LiveKit; `owner` — принципал владельца из метаданных комнаты. */
export function personOf(participant: Participant, isLocal: boolean, owner: string | null): CallPerson {
  return {
    identity: participant.identity,
    name: participant.name ? participant.name : participant.identity,
    isLocal,
    isOwner: owner !== null && principalOf(participant.identity) === owner,
    micOn: live(participant, Track.Source.Microphone),
    cameraOn: live(participant, Track.Source.Camera),
    screenOn: live(participant, Track.Source.ScreenShare),
    speaking: participant.isSpeaking,
    lastSpokeAt: participant.lastSpokeAt?.getTime() ?? 0,
    hand: participant.attributes.hand ? participant.attributes.hand : null,
  };
}

/** Люди звонка: сам человек первым, остальные в порядке входа, без технических участников (egress). */
export function callPeopleOf(local: Participant, remote: Iterable<Participant>, owner: string | null): CallPerson[] {
  const others = [...remote].toSorted((a, b) => (a.joinedAt?.getTime() ?? 0) - (b.joinedAt?.getTime() ?? 0));
  return peopleOf([personOf(local, true, owner), ...others.map((participant) => personOf(participant, false, owner))]);
}
