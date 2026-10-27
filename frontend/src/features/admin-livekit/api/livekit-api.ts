import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type { LiveKitOverview, LiveKitRoomDetail } from "../domain/contract";

const room = (name: string) => ({ params: { path: { name } } });

export const livekitApi = {
  overview: (): Promise<LiveKitOverview> => dataOf(apiClient.GET("/v1/admin/livekit/overview")),
  room: (name: string): Promise<LiveKitRoomDetail> =>
    dataOf(apiClient.GET("/v1/admin/livekit/rooms/{name}", room(name))),
  endRoom: (name: string): Promise<void> => dataOf(apiClient.DELETE("/v1/admin/livekit/rooms/{name}", room(name))),
  removeParticipant: (name: string, identity: string): Promise<void> =>
    dataOf(
      apiClient.DELETE("/v1/admin/livekit/rooms/{name}/participants/{identity}", {
        params: { path: { name, identity } },
      }),
    ),
};
