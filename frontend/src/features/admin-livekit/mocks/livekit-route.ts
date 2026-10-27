import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import type { LiveKitOverview, LiveKitRoomDetail } from "../domain/contract";
import { deleteRoom, getOverview, getRoom, removeParticipant } from "./demo-store";

/* Обработчики /v1/admin/livekit/* поверх демо в памяти: для тестов и разработки без бэкенда. */

type RoomContext = { params: Promise<{ name: string }> };
type ParticipantContext = { params: Promise<{ name: string; identity: string }> };

/** Имя комнаты и identity LiveKit: до 256 символов, без управляющих символов и слэшей, как у бэкенда. */
const segment = z
  .string()
  .min(1)
  .max(256)
  .regex(/^[^/\p{Cc}]+$/u);

const participantParams = z.object({ name: segment, identity: segment });

/** Отказ в конверте ошибок платформы (ADR 0008). */
const refused = (code: string, status: number) =>
  Response.json({ error: { code, request_id: "mock-request" }, detail: code }, { status });

/** /v1/admin/livekit/overview */
export const livekitOverviewRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<LiveKitOverview>(getOverview());
  },
};

/** /v1/admin/livekit/rooms/{name} */
export const livekitRoomRoute = {
  async GET(_request: Request, { params }: RoomContext) {
    const name = segment.safeParse((await params).name);
    if (!name.success) return refused("validation_error", 422);
    const room = getRoom(name.data);
    return room ? JsonResponse.json<LiveKitRoomDetail>(room) : refused("room_not_found", 404);
  },

  async DELETE(_request: Request, { params }: RoomContext) {
    const name = segment.safeParse((await params).name);
    if (!name.success) return refused("validation_error", 422);
    return deleteRoom(name.data) ? new Response(null, { status: 204 }) : refused("room_not_found", 404);
  },
};

/** /v1/admin/livekit/rooms/{name}/participants/{identity} */
export const livekitParticipantRoute = {
  async DELETE(_request: Request, { params }: ParticipantContext) {
    const parsed = participantParams.safeParse(await params);
    if (!parsed.success) return refused("validation_error", 422);
    const { name, identity } = parsed.data;
    const result = removeParticipant(name, identity);
    if (result === "no-room") return refused("room_not_found", 404);
    if (result === "no-participant") return refused("participant_not_found", 404);
    return new Response(null, { status: 204 });
  },
};
