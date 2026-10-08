import { z } from "zod";

import { detail, JsonResponse } from "@/mocks/runtime";

import type { LiveKitOverview, LiveKitRoomDetail } from "../domain/contract";
import { deleteRoom, getOverview, getRoom, removeParticipant } from "./demo-store";

/* Route handlers for /api/admin/livekit/*: the backend when configured, the in-memory demo otherwise. */

type RoomContext = { params: Promise<{ name: string }> };
type ParticipantContext = { params: Promise<{ name: string; identity: string }> };

/** LiveKit room names (and participant identities): up to 256 characters, no control characters or slashes. */
const segment = z
  .string()
  .min(1)
  .max(256)
  .regex(/^[^/\p{Cc}]+$/u);

const participantParams = z.object({ name: segment, identity: segment });

/** /api/admin/livekit/overview */
export const livekitOverviewRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<LiveKitOverview>(getOverview());
  },
};

/** /api/admin/livekit/rooms/[name] */
export const livekitRoomRoute = {
  async GET(_request: Request, { params }: RoomContext) {
    const name = segment.safeParse((await params).name);
    if (!name.success) return detail("Некорректное имя комнаты.", 422);
    const room = getRoom(name.data);
    return room ? JsonResponse.json<LiveKitRoomDetail>(room) : detail("Комната не найдена или уже завершена.", 404);
  },

  async DELETE(_request: Request, { params }: RoomContext) {
    const name = segment.safeParse((await params).name);
    if (!name.success) return detail("Некорректное имя комнаты.", 422);
    return deleteRoom(name.data)
      ? new Response(null, { status: 204 })
      : detail("Комната не найдена или уже завершена.", 404);
  },
};

/** /api/admin/livekit/rooms/[name]/participants/[identity] */
export const livekitParticipantRoute = {
  async DELETE(_request: Request, { params }: ParticipantContext) {
    const parsed = participantParams.safeParse(await params);
    if (!parsed.success) return detail("Некорректная комната или участник.", 422);
    const { name, identity } = parsed.data;
    const result = removeParticipant(name, identity);
    if (result === "no-room") return detail("Комната не найдена или уже завершена.", 404);
    if (result === "no-participant") return detail("Участник уже покинул комнату.", 404);
    return new Response(null, { status: 204 });
  },
};
