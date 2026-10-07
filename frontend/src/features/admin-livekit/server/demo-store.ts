import type {
  LiveKitHealth,
  LiveKitNode,
  LiveKitOverview,
  LiveKitRoom,
  LiveKitRoomDetail,
  LiveKitServer,
} from "../domain/contract";
import { type DemoRoom, type DemoState, makeParticipant, makeRoom } from "./demo-factory";
import {
  DEMO_NODES,
  DEMO_UPTIME_MS,
  FINISHED_EGRESS,
  MBPS_IN_PER_PARTICIPANT,
  MBPS_OUT_PER_PARTICIPANT,
  MINUTE,
  OPEN_ROOMS,
  RECORDING_BYTES_PER_MINUTE,
} from "./demo-fixtures";
import { clamp, demoHistory, iso, jitter, pick, round1, shortId } from "./demo-history";

/*
 * In-memory LiveKit server for the demo. Rooms, participants and nodes drift a little on every
 * overview request so the dashboard feels live. The server URL and whether API credentials are
 * set come from the real env; the key and secret themselves are never read into a response.
 */

function seed(): DemoState {
  const now = Date.now();
  const state: DemoState = {
    rooms: new Map(),
    nodes: structuredClone(DEMO_NODES),
    egress: [],
    startedAt: now - DEMO_UPTIME_MS,
    nextPerson: 0,
    nextRoom: 0,
  };
  for (const [title, ago, minutes, status] of FINISHED_EGRESS) {
    const bytes = Math.round(minutes * RECORDING_BYTES_PER_MINUTE * (0.9 + Math.random() * 0.2));
    state.egress.push({
      id: `EG_${shortId()}`,
      room_name: `leo-mtg-${shortId()}`,
      room_title: title,
      status,
      started_at: iso(now - ago),
      ended_at: iso(now - ago + Math.max(minutes, 2) * MINUTE),
      file_size_bytes: status === "complete" ? bytes : null,
    });
  }
  for (const [minutesAgo, size, recording] of OPEN_ROOMS) {
    const room = makeRoom(state, now - minutesAgo * MINUTE, size, recording);
    state.rooms.set(room.room.name, room);
  }
  return state;
}

const shared = globalThis as typeof globalThis & { adminDemoLiveKit?: DemoState };
shared.adminDemoLiveKit ??= seed();
const state = shared.adminDemoLiveKit;

/** Small random changes between polls: people join and leave, rooms open, load moves. */
function drift(now: number) {
  const rooms = [...state.rooms.values()];
  const roll = Math.random();
  if (roll < 0.25 && rooms.length > 0) {
    const room = pick(rooms);
    if (room.participants.length < 12) room.participants.push(makeParticipant(state, now, false));
  } else if (roll < 0.42 && rooms.length > 0) {
    const room = pick(rooms);
    if (room.participants.length > 2) room.participants.splice(Math.floor(Math.random() * room.participants.length), 1);
  } else if (roll < 0.5 && rooms.length < 7) {
    const room = makeRoom(state, now, 2 + Math.floor(Math.random() * 3), Math.random() < 0.25);
    state.rooms.set(room.room.name, room);
  }
  for (const room of rooms)
    for (const participant of room.participants)
      if (Math.random() < 0.08) {
        const audio = participant.tracks.find((track) => track.kind === "audio");
        if (audio) audio.muted = !audio.muted;
      }
  for (const egress of state.egress) if (egress.status === "starting") egress.status = "active";
}

function health(nodes: LiveKitNode[]): LiveKitHealth {
  const down = nodes.filter((node) => node.state === "down").length;
  if (down === nodes.length) return "down";
  return down > 0 ? "degraded" : "healthy";
}

function serverInfo(nodes: LiveKitNode[]): LiveKitServer {
  return {
    url: process.env.LIVEKIT_URL || "wss://meet.leo.example",
    version: "1.8.4",
    region: "Москва",
    started_at: iso(state.startedAt),
    health: health(nodes),
    api_key_configured: Boolean(process.env.LIVEKIT_API_KEY && process.env.LIVEKIT_API_SECRET),
    demo: true,
  };
}

const toRoom = ({ room, participants }: DemoRoom): LiveKitRoom => ({ ...room, num_participants: participants.length });

export function getOverview(): LiveKitOverview {
  const now = Date.now();
  drift(now);
  const rooms = [...state.rooms.values()];
  const nodes = state.nodes.map(({ cpu_base, memory_base, ...node }): LiveKitNode => {
    const hosted = rooms.filter((room) => room.node === node.id);
    const participants = hosted.reduce((sum, room) => sum + room.participants.length, 0);
    return {
      ...node,
      rooms: hosted.length,
      participants,
      cpu_percent: round1(clamp(cpu_base + participants * 3.2 + jitter(3), 1, 99)),
      memory_percent: round1(clamp(memory_base + participants * 0.8 + jitter(1.5), 5, 99)),
    };
  });
  const participants = rooms.reduce((sum, room) => sum + room.participants.length, 0);
  const tracks = rooms.reduce(
    (sum, room) => sum + room.participants.reduce((inner, participant) => inner + participant.tracks.length, 0),
    0,
  );
  const factor = 0.92 + Math.random() * 0.16;
  const bandwidthIn = round1(participants * MBPS_IN_PER_PARTICIPANT * factor);
  const bandwidthOut = round1(participants * MBPS_OUT_PER_PARTICIPANT * factor);
  return {
    server: serverInfo(nodes),
    stats: {
      active_rooms: rooms.length,
      participants,
      published_tracks: tracks,
      bandwidth_in_mbps: bandwidthIn,
      bandwidth_out_mbps: bandwidthOut,
      active_egress: state.egress.filter((egress) => egress.status === "starting" || egress.status === "active").length,
    },
    history: demoHistory(now, {
      at: iso(now),
      participants,
      bandwidth_in_mbps: bandwidthIn,
      bandwidth_out_mbps: bandwidthOut,
    }),
    nodes,
    rooms: rooms.map(toRoom).toSorted((a, b) => b.started_at.localeCompare(a.started_at)),
    egress: state.egress.slice(0, 12),
    updated_at: iso(now),
  };
}

export function getRoom(name: string): LiveKitRoomDetail | null {
  const room = state.rooms.get(name);
  return room ? { ...toRoom(room), participants: structuredClone(room.participants) } : null;
}

/** Ends the room for everyone; a running recording is finalised. */
export function deleteRoom(name: string): boolean {
  const room = state.rooms.get(name);
  if (!room) return false;
  state.rooms.delete(name);
  const now = Date.now();
  for (const egress of state.egress) {
    if (egress.room_name !== name || egress.ended_at !== null) continue;
    egress.status = "complete";
    egress.ended_at = iso(now);
    egress.file_size_bytes = Math.round(((now - Date.parse(egress.started_at)) / MINUTE) * RECORDING_BYTES_PER_MINUTE);
  }
  return true;
}

export function removeParticipant(name: string, identity: string): "removed" | "no-room" | "no-participant" {
  const room = state.rooms.get(name);
  if (!room) return "no-room";
  const index = room.participants.findIndex((participant) => participant.identity === identity);
  if (index === -1) return "no-participant";
  room.participants.splice(index, 1);
  return "removed";
}
