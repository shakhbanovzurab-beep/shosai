import { apiRequest } from "@/lib/api/request";

import type { LiveKitOverview, LiveKitRoomDetail } from "../domain/contract";

const BASE = "/api/admin/livekit";
const room = (name: string) => `${BASE}/rooms/${encodeURIComponent(name)}`;

export const livekitApi = {
  overview: () => apiRequest<LiveKitOverview>(`${BASE}/overview`),
  room: (name: string) => apiRequest<LiveKitRoomDetail>(room(name)),
  endRoom: (name: string) => apiRequest<void>(room(name), { method: "DELETE" }),
  removeParticipant: (name: string, identity: string) =>
    apiRequest<void>(`${room(name)}/participants/${encodeURIComponent(identity)}`, { method: "DELETE" }),
};
