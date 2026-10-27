// Моки /v1/admin/livekit/*: API опубликован (meetings A8), моки остаются для тестов и разработки без бэкенда.
import { type MockRoute, mockRoute } from "@/mocks/routing";

import { livekitOverviewRoute, livekitParticipantRoute, livekitRoomRoute } from "./livekit-route";

export const handlers: MockRoute[] = [
  mockRoute("/v1/admin/livekit/overview", livekitOverviewRoute, ["GET"]),
  mockRoute("/v1/admin/livekit/rooms/:name", livekitRoomRoute, ["GET", "DELETE"]),
  mockRoute("/v1/admin/livekit/rooms/:name/participants/:identity", livekitParticipantRoute, ["DELETE"]),
];
