/**
 * Admin › LiveKit API contract, shared by the dashboard and the route handlers in
 * `server/livekit-route.ts` (mounted under `src/app/api/admin/livekit`). They proxy to
 * `${BACKEND_API_URL}/v1/admin/livekit/*` when it is set and fall back to an in-memory demo otherwise.
 * snake_case to match Pydantic; errors are FastAPI's `{ "detail": string }`. Times are ISO 8601
 * strings in UTC.
 *
 * The backend talks to the LiveKit server with `LIVEKIT_URL`, `LIVEKIT_API_KEY` and
 * `LIVEKIT_API_SECRET`; the key and secret never leave the server, only whether they are set.
 */

/* ---------- GET /admin/livekit/overview ---------- */

export type LiveKitHealth = "healthy" | "degraded" | "down";

export type LiveKitServer = {
  /** The signalling URL clients connect to, e.g. `wss://meet.example.com`; null when not configured. */
  url: string | null;
  version: string | null;
  region: string | null;
  /** When the longest-running node started; uptime is counted from it. */
  started_at: string | null;
  health: LiveKitHealth;
  /** Both `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` are set on the server. */
  api_key_configured: boolean;
  /** The numbers come from the built-in demo, not a real server. */
  demo: boolean;
};

export type LiveKitStats = {
  active_rooms: number;
  participants: number;
  published_tracks: number;
  bandwidth_in_mbps: number;
  bandwidth_out_mbps: number;
  /** Egress jobs (recordings, streams) that are starting or running. */
  active_egress: number;
};

/** One sample of the last 24 hours, oldest first. */
export type LiveKitHistoryPoint = {
  at: string;
  participants: number;
  bandwidth_in_mbps: number;
  bandwidth_out_mbps: number;
};

export type LiveKitNodeState = "serving" | "draining" | "down";

export type LiveKitNode = {
  id: string;
  region: string;
  cpu_percent: number;
  memory_percent: number;
  rooms: number;
  participants: number;
  state: LiveKitNodeState;
};

export type LiveKitRoom = {
  /** LiveKit room name, unique while the room is open; used in the URLs below. */
  name: string;
  /** The Leo meeting title. */
  title: string;
  started_at: string;
  num_participants: number;
  recording: boolean;
  /** Codecs in use by the room's published tracks, e.g. "VP8", "Opus". */
  video_codec: string | null;
  audio_codec: string | null;
};

export type LiveKitEgressStatus = "starting" | "active" | "ending" | "complete" | "failed";

export type LiveKitEgress = {
  id: string;
  room_name: string;
  room_title: string;
  status: LiveKitEgressStatus;
  started_at: string;
  ended_at: string | null;
  /** Null until the file has been written. */
  file_size_bytes: number | null;
};

export type LiveKitOverview = {
  server: LiveKitServer;
  stats: LiveKitStats;
  /** 24 hours of samples, oldest first; the last one is the current moment. */
  history: LiveKitHistoryPoint[];
  nodes: LiveKitNode[];
  rooms: LiveKitRoom[];
  /** Recent egress jobs, newest first. */
  egress: LiveKitEgress[];
  /** When the backend took this snapshot; the dashboard measures durations from it. */
  updated_at: string;
};

/* ---------- GET /admin/livekit/rooms/{name} ---------- */

export type ConnectionQuality = "excellent" | "good" | "poor" | "lost";

export type TrackKind = "audio" | "video" | "screen";

export type LiveKitTrack = { sid: string; kind: TrackKind; muted: boolean };

export type DeviceOs = "macos" | "windows" | "linux" | "ios" | "android";

/** Reported by Leo clients in participant attributes when they join. */
export type LiveKitDevice = {
  os: DeviceOs;
  os_version: string;
  /** "desktop" for the Leo apps on macOS and Windows, "web" for a browser tab. */
  client: "desktop" | "web" | "mobile";
  client_version: string | null;
  /** Browser and version for web clients, e.g. "Chrome 141". */
  browser: string | null;
};

export type LiveKitParticipant = {
  identity: string;
  name: string;
  joined_at: string;
  device: LiveKitDevice;
  connection_quality: ConnectionQuality;
  tracks: LiveKitTrack[];
};

export type LiveKitRoomDetail = LiveKitRoom & { participants: LiveKitParticipant[] };

/* ---------- DELETE /admin/livekit/rooms/{name} → 204: ends the room for everyone ---------- */
/* ---------- DELETE /admin/livekit/rooms/{name}/participants/{identity} → 204 ---------- */

/** Dashboard refresh interval while the tab is visible. */
export const LIVEKIT_POLL_MS = 10_000;
