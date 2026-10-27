import type { components } from "@/lib/api/generated/schema";

/**
 * Что сервер отдаёт администратору о LiveKit (`/v1/admin/livekit/*`, MR-D10): только API LiveKit и
 * Prometheus, без содержимого встреч — комната называется именем LiveKit, названия встречи нет.
 * Чего LiveKit не сообщает (версия, регион, качество связи), в контракте нет; null — «нет данных».
 */
type Schemas = components["schemas"];

export type LiveKitOverview = Schemas["LiveKitOverviewOut"];
export type LiveKitServer = Schemas["LiveKitServerOut"];
export type LiveKitHealth = Schemas["LiveKitHealth"];
export type LiveKitStats = Schemas["LiveKitStatsOut"];
export type LiveKitHistoryPoint = Schemas["LiveKitHistoryPointOut"];
export type LiveKitNode = Schemas["LiveKitNodeOut"];
export type LiveKitNodeState = LiveKitNode["state"];
export type LiveKitRoom = Schemas["LiveKitRoomOut"];
export type LiveKitEgress = Schemas["LiveKitEgressOut"];
export type LiveKitEgressStatus = LiveKitEgress["status"];
export type LiveKitRoomDetail = Schemas["LiveKitRoomDetailOut"];
export type LiveKitParticipant = Schemas["LiveKitParticipantOut"];
export type LiveKitDevice = Schemas["LiveKitDeviceOut"];
export type LiveKitTrack = Schemas["LiveKitTrackOut"];

/** Интервал обновления экрана, пока вкладка видна. */
export const LIVEKIT_POLL_MS = 10_000;
