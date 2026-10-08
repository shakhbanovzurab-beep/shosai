import type { LiveKitEgress, LiveKitParticipant, LiveKitRoom, LiveKitTrack } from "../domain/contract";
import { type DEMO_NODES, DEVICES, MEETINGS, MINUTE, PEOPLE, QUALITY_STEPS, VIDEO_CODECS } from "./demo-fixtures";
import { iso, pick, shortId } from "./demo-history";

/* Builds demo rooms and participants for the in-memory LiveKit demo in `demo-store.ts`. */

export type DemoRoom = {
  room: Omit<LiveKitRoom, "num_participants">;
  node: string;
  participants: LiveKitParticipant[];
};
export type DemoState = {
  rooms: Map<string, DemoRoom>;
  nodes: typeof DEMO_NODES;
  egress: LiveKitEgress[];
  startedAt: number;
  nextPerson: number;
  nextRoom: number;
};

export function makeParticipant(state: DemoState, joinedAt: number, withScreen: boolean): LiveKitParticipant {
  const [name, slug] = PEOPLE[state.nextPerson % PEOPLE.length] ?? PEOPLE[0];
  // Identities are unique within a room, so a second lap through the list gets a suffix.
  const lap = Math.floor(state.nextPerson / PEOPLE.length);
  state.nextPerson += 1;
  const device = pick(DEVICES);
  const tracks: LiveKitTrack[] = [{ sid: `TR_A${shortId()}`, kind: "audio", muted: Math.random() < 0.4 }];
  if (Math.random() < 0.8) tracks.push({ sid: `TR_V${shortId()}`, kind: "video", muted: Math.random() < 0.15 });
  if (withScreen) tracks.push({ sid: `TR_S${shortId()}`, kind: "screen", muted: false });
  const quality = Math.random();
  return {
    identity: lap === 0 ? `usr_${slug}` : `usr_${slug}_${lap + 1}`,
    name,
    joined_at: iso(joinedAt),
    device,
    connection_quality: QUALITY_STEPS.find(([limit]) => quality < limit)?.[1] ?? "lost",
    tracks,
  };
}

export function makeRoom(state: DemoState, startedAt: number, size: number, recording: boolean): DemoRoom {
  const title = MEETINGS[state.nextRoom % MEETINGS.length] ?? MEETINGS[0];
  state.nextRoom += 1;
  const name = `leo-mtg-${shortId()}`;
  const participants = Array.from({ length: size }, (_, index) =>
    makeParticipant(state, startedAt + index * 40_000, index === 0 && Math.random() < 0.5),
  );
  const node = pick(state.nodes.filter((n) => n.state === "serving")).id;
  const room = {
    name,
    title,
    started_at: iso(startedAt),
    recording,
    video_codec: pick(VIDEO_CODECS),
    audio_codec: "Opus",
  };
  if (recording)
    state.egress.unshift({
      id: `EG_${shortId()}`,
      room_name: name,
      room_title: title,
      status: "active",
      started_at: iso(startedAt + MINUTE),
      ended_at: null,
      file_size_bytes: null,
    });
  return { room, node, participants };
}
