import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

type Schemas = components["schemas"];
export type TranscriptPageOut = Schemas["Page_TranscriptLineOut_"];
export type TranscriptLineOut = Schemas["TranscriptLineOut"];
export type WriteUpOut = Schemas["WriteUpOut"];
export type SectionOut = Schemas["SectionOut"];
export type FindingOut = Schemas["FindingOut"];
export type MapPageOut = Schemas["Page_MapNodeOut_"];
export type MapNodeOut = Schemas["MapNodeOut"];
export type MyNotesOut = Schemas["MyNotesOut"];
export type ParticipantOut = Schemas["ParticipantOut"];

// Самые большие страницы, что отдаёт сервер: расшифровка и карта читаются целиком за несколько запросов.
const TRANSCRIPT_PAGE = 500;
const MAP_PAGE = 100;

const meeting = (id: string) => ({ params: { path: { meeting_id: id } } });

/** Содержимое встречи на `/v1/notes/{id}/…`: расшифровка, запись Leo, карта, свои заметки и участники. */
export const contentApi = {
  transcript: (id: string, cursor?: string): Promise<TranscriptPageOut> =>
    dataOf(
      apiClient.GET("/v1/notes/{meeting_id}/transcript", {
        params: { path: { meeting_id: id }, query: { cursor, limit: TRANSCRIPT_PAGE } },
      }),
    ),
  writeUp: (id: string): Promise<WriteUpOut> => dataOf(apiClient.GET("/v1/notes/{meeting_id}/write-up", meeting(id))),
  /** Переписывает запись по шаблону: ключ — одно действие человека, повтор запроса даёт тот же прогон. */
  rewrite: (id: string, templateId: string, key: string): Promise<Schemas["RewriteAccepted"]> =>
    dataOf(
      apiClient.POST("/v1/notes/{meeting_id}/write-up", {
        params: { path: { meeting_id: id }, header: { "Idempotency-Key": key } },
        body: { template_id: templateId },
      }),
    ),
  map: (id: string, cursor?: string): Promise<MapPageOut> =>
    dataOf(
      apiClient.GET("/v1/notes/{meeting_id}/map", {
        params: { path: { meeting_id: id }, query: { cursor, limit: MAP_PAGE } },
      }),
    ),
  myNotes: (id: string): Promise<MyNotesOut> => dataOf(apiClient.GET("/v1/notes/{meeting_id}/my-notes", meeting(id))),
  saveMyNotes: (id: string, text: string): Promise<MyNotesOut> =>
    dataOf(apiClient.PUT("/v1/notes/{meeting_id}/my-notes", { ...meeting(id), body: { text } })),
  addParticipant: (id: string, email: string): Promise<ParticipantOut> =>
    dataOf(apiClient.POST("/v1/notes/{meeting_id}/participants", { ...meeting(id), body: { email } })),
  removeParticipant: (id: string, participantId: string): Promise<void> =>
    dataOf(
      apiClient.DELETE("/v1/notes/{meeting_id}/participants/{participant_id}", {
        params: { path: { meeting_id: id, participant_id: participantId } },
      }),
    ),
};
